"""Prepare explicitly synthetic M4 integration inputs on SageMaker, not benchmarks."""
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def prepare(destination, boundary=False):
    import numpy as np
    from PIL import Image
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(2026)
    for kind in ('classification','segmentation'):
        spec={'kind':kind,'channels':3,'height':32,'width':32,'classes':2,
              'class_names':['red','blue'] if kind=='classification' else ['background','blue_rectangle'],
              'description':'Synthetic M4 '+kind+' integration fixture; not an accuracy benchmark',
              'band_names':['R','G','B'],'rgb_indices':[0,1,2],'input_divisors':[255,255,255],
              'primary_metric':'accuracy' if kind=='classification' else 'macro_iou','ignore_index':None}
        rows={'train':[],'valid':[]}; files={}
        for split,count in (('train',8),('valid',4)):
            for index in range(count):
                pixels=rng.integers(0,18,(32,32,3),dtype='uint8')
                if kind=='classification':
                    label=index%2; pixels[:,:,0 if label==0 else 2]+=220
                    target={'label':label}
                else:
                    mask=np.zeros((32,32),dtype='uint8')
                    offset=3+index
                    mask[offset:offset+12,8:23]=1
                    pixels[:]+=60; pixels[mask==1]=[15,30,240]
                    mask_name=split+'/'+str(index)+'-mask.png'
                    buf=io.BytesIO(); Image.fromarray(mask).save(buf,format='PNG'); files[mask_name]=buf.getvalue()
                    target={'mask':mask_name}
                name=split+'/'+str(index)+'.png'
                buf=io.BytesIO(); Image.fromarray(pixels).save(buf,format='PNG'); files[name]=buf.getvalue()
                rows[split].append({'image':name,**target})
        manifest={'task':spec,'splits':rows}
        with zipfile.ZipFile(destination/('m4-'+kind+'.zip'),'x',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(manifest))
            for name,data in files.items(): archive.writestr(name,data)
        (destination/('m4-'+kind+'-image.png')).write_bytes(files['valid/0.png'])
    if boundary:
        # A referenced valid TIFF may contain padding; no extra archive members.
        spec={**spec,'kind':'classification','primary_metric':'accuracy','class_names':['a','b'],
              'description':'Synthetic transport-boundary fixture; do not train'}
        rows={split:[{'image':split+'.tif','label':0 if split=='train' else 1}] for split in ('train','valid')}
        buf=io.BytesIO(); Image.fromarray(np.zeros((32,32,3),dtype='uint8')).save(buf,format='TIFF'); image=buf.getvalue()
        manifest=json.dumps({'task':spec,'splits':rows}).encode()
        path=destination/'m4-boundary-32MiB.zip'
        def write(padding):
            with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED) as archive:
                archive.writestr('manifest.json',manifest)
                archive.writestr('train.tif',image)
                archive.writestr('valid.tif',image+b'\0'*padding)
        write(0); write(32*2**20-path.stat().st_size)
        assert path.stat().st_size==32*2**20
    print(json.dumps({p.name:p.stat().st_size for p in destination.iterdir() if p.is_file()},indent=2))


if __name__=='__main__':
    if ROOT!=Path('/home/sagemaker-user/GoTrain'): raise RuntimeError('Prepare ML inputs only on SageMaker')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path); parser.add_argument('--boundary',action='store_true')
    args=parser.parse_args(); prepare(args.destination,args.boundary)
