"""The two already-calibrated model families; no implicit weight downloads."""
import torch
from torchvision.models import resnet18
from torchvision.models.segmentation import fcn_resnet50


def build_model(name, spec):
    if name == 'resnet18' and spec['kind'] == 'classification':
        model = resnet18(weights=None, num_classes=spec['classes'])
        stem = model
    elif name == 'fcn_resnet50' and spec['kind'] == 'segmentation':
        model = fcn_resnet50(weights=None, weights_backbone=None, num_classes=spec['classes'], aux_loss=False)
        stem = model.backbone
    else:
        raise ValueError('Unsupported model/task pairing')
    if spec['channels'] != 3:
        stem.conv1 = torch.nn.Conv2d(spec['channels'], 64, 7, stride=2, padding=3, bias=False)
    return model


def logits_for(model, x, spec):
    output = model(x)
    logits = output['out'] if isinstance(output, dict) else output
    expected = (x.shape[0], spec['classes'], *x.shape[-2:]) if spec['kind'] == 'segmentation' else (x.shape[0], spec['classes'])
    if tuple(logits.shape) != expected or not torch.isfinite(logits).all():
        raise ValueError('Invalid model output shape or non-finite logits')
    return logits
