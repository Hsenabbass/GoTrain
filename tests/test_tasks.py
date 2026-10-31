"""Task/model acceptance checks; SageMaker CPU only, reviewed cached weights."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
from PIL import Image
import rasterio
from rasterio.transform import from_origin
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gotrain.data import ManifestData, prepare, task_spec, validate_task, fit_normalization
from gotrain.models import CANDIDATES, candidate_info, candidate_normalization, build_candidate, logits_for, set_training_mode
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'artifacts/weights/m3'


def spec(kind='classification', channels=3):
    return {'kind':kind, 'channels':channels, 'height':32, 'width':48,
            'classes':3, 'input_divisors':[255]*channels,
            'band_names':['R','G','B','NIR'][:channels], 'rgb_indices':[0,1,2],
            'primary_metric':'accuracy' if kind=='classification' else 'macro_iou', 'ignore_index':None}


class TaskChecks(unittest.TestCase):
    def test_frozen_benchmark_contracts(self):
        contracts=json.loads((ROOT/'configs/tasks.json').read_text());original=copy.deepcopy(contracts)
        inspection=json.loads((ROOT/'docs/data-inspection.json').read_text())
        for task in contracts['tasks']:
            got=task_spec(task,contracts,inspection)
            self.assertEqual(got['channels'],contracts['tasks'][task]['channels'])
            self.assertEqual(got['rgb_indices'],[3,2,1] if task in ('m-eurosat','m-brick-kiln') else [0,1,2])
        self.assertEqual(contracts,original)

    def test_manifest_classification_and_split_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n in ('train','valid'):Image.fromarray(np.full((32,48,3),255,np.uint8)).save(root/(n+'.png'))
            value={'task':spec(),'splits':{'train':[{'image':'train.png','label':2}],'valid':[{'image':'valid.png','label':1}]}}
            p=root/'manifest.json';p.write_text(json.dumps(value))
            train=ManifestData(p,'train');x,y=train[0];self.assertEqual(tuple(x.shape),(3,32,48));self.assertEqual(y.item(),2)
            self.assertTrue((x==1).all());self.assertEqual(fit_normalization(train)['fitted_on'],'train')
            with self.assertRaises(ValueError):ManifestData('/missing','test')
            with self.assertRaises(ValueError):ManifestData(p,'valid',augment=True)
            for name in ('../outside.png','/tmp/outside.png','train.png'):
                value['splits']['valid'][0]['image']=name;p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):ManifestData(p,'valid')

    def test_multiband_segmentation_alignment_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shape=(32,48);transform=from_origin(0,32,1,1)
            for split in ('train','valid'):
                with rasterio.open(root/(split+'.tif'),'w',driver='GTiff',height=32,width=48,count=4,dtype='uint8',crs='EPSG:4326',transform=transform) as f:f.write(np.full((4,*shape),255,np.uint8))
                with rasterio.open(root/(split+'-mask.tif'),'w',driver='GTiff',height=32,width=48,count=1,dtype='uint8',crs='EPSG:4326',transform=transform) as f:f.write(np.full(shape,2,np.uint8),1)
            p=root/'manifest.json';value={'task':spec('segmentation',4),'splits':{s:[{'image':s+'.tif','mask':s+'-mask.tif'}] for s in ('train','valid')}};p.write_text(json.dumps(value))
            x,y=ManifestData(p,'train',True)[0];self.assertEqual(tuple(x.shape),(4,32,48));self.assertEqual(tuple(y.shape),shape);self.assertTrue((y==2).all())
            with rasterio.open(root/'train-mask.tif','r+') as f:f.transform=from_origin(1,32,1,1)
            with self.assertRaises(ValueError):ManifestData(p,'train')[0]
            for target in (np.full(shape,3,np.uint8),np.zeros(shape,np.float32)):
                with self.assertRaises(ValueError):prepare(np.zeros((4,*shape)),target,value['task'])

    def test_pretrained_normalization(self):
        s=spec('segmentation',4)
        with self.assertRaises(ValueError):candidate_normalization('fcn_imagenet',s)
        n=candidate_normalization('fcn_imagenet',s,{'fitted_on':'train','mean':[1,2,3,.2],'std':[1,1,1,.1]})
        x,y=prepare(np.full((4,32,48),255,np.uint8),np.zeros((32,48),np.uint8),s,n)
        self.assertAlmostEqual(x[0,0,0].item(),(1-.485)/.229,places=5)
        self.assertAlmostEqual(x[3,0,0].item(),8,places=5)
        s['rgb_indices']=[3,2,1];n=candidate_normalization('fcn_imagenet',s,{'fitted_on':'train','mean':[.1]*4,'std':[.2]*4})
        self.assertEqual(n['mean'][3],.485);self.assertEqual(n['mean'][0],.1)

    def test_candidate_admission(self):
        s=spec();info=candidate_info('resnet18_imagenet',s)
        with self.assertRaises(ValueError):candidate_info('fcn_imagenet',s)
        with self.assertRaises(ValueError):candidate_info('resnet18_imagenet',{**s,'rgb_indices':None})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.pt';p.write_bytes(b'not a weight')
            r={'url':info['url'],'weight_id':info['weight_id'],'terms_reviewed':True,'target_finetuned':False,'heldout_overlap':'none_known','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for change in ({'target_finetuned':True},{'heldout_overlap':'known'},{'url':'https://other.invalid'},{'sha256':'bad'},{'terms_reviewed':False}):
                with self.assertRaises(ValueError):build_candidate('resnet18_imagenet',s,p,{**r,**change})

    def test_real_reviewed_backbones(self):
        torch.set_num_threads(2)
        receipts=json.loads((CACHE/'receipts.json').read_text())
        for candidate, (kind,_,_) in CANDIDATES.items():
            with self.subTest(candidate=candidate):
                s=spec(kind,4 if kind=='segmentation' else 3)
                if candidate=='resnet18_imagenet':s['rgb_indices']=[2,1,0]
                receipt=receipts[candidate]
                model=build_candidate(candidate,s,CACHE/receipt['filename'],receipt,head_only=True)
                model.eval()
                with torch.no_grad():output=logits_for(model,torch.ones(1,s['channels'],32,48),s)
                self.assertEqual(output.shape[1],3)
                self.assertTrue(all(p.device.type=='cpu' for p in model.parameters()))
                set_training_mode(model)
                self.assertFalse(any(m.training for m in model.modules() if isinstance(m,torch.nn.BatchNorm2d)))
                with torch.no_grad():self.assertTrue(torch.isfinite(logits_for(model,torch.ones(1,s['channels'],32,48),s)).all())
                self.assertTrue(any(p.requires_grad for p in model.parameters()));self.assertTrue(any(not p.requires_grad for p in model.parameters()))
                del model
