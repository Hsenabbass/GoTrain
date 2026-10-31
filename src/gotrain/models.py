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


# All pretrained choices use ImageNet backbones, not target-finetuned task heads.
# Paths/receipts are supplied by reviewed operator code, never by Claude.
CANDIDATES = {
    'resnet18_imagenet': ('classification', 'ResNet18_Weights', 'IMAGENET1K_V1'),
    'mobilenet_small_imagenet': ('classification', 'MobileNet_V3_Small_Weights', 'IMAGENET1K_V1'),
    'fcn_imagenet': ('segmentation', 'ResNet50_Weights', 'IMAGENET1K_V1'),
    'deeplab_mobile_imagenet': ('segmentation', 'MobileNet_V3_Large_Weights', 'IMAGENET1K_V1'),
}


def candidate_info(candidate, spec):
    """Admit architecture/bands; return weight metadata without downloading."""
    from torchvision import models
    from .data import validate_task
    validate_task(spec)
    kind, enum, version = CANDIDATES[candidate]
    if kind != spec['kind'] or spec.get('rgb_indices') is None:
        raise ValueError('Candidate needs matching task and verified RGB mapping')
    weight = getattr(getattr(models, enum), version)
    transform = weight.transforms()
    return {'id': candidate, 'kind': kind, 'weight_id': enum + '.' + version,
            'url': weight.url, 'pretraining': 'ImageNet-1K',
            'mean': transform.mean, 'std': transform.std,
            'geometry': 'native_grid_no_crop', 'adaptation': 'copy_verified_RGB_random_extra_channels',
            'terms': 'https://docs.pytorch.org/vision/0.24/models.html#general-information-on-pre-trained-weights'}


def candidate_normalization(candidate, spec, training=None):
    """Checkpoint RGB statistics after per-band scaling; train-fitted extras."""
    info = candidate_info(candidate, spec)
    rgb = spec['rgb_indices']
    if spec['channels'] > 3:
        if not training or training.get('fitted_on') != 'train':
            raise ValueError('Extra channels need train-fitted statistics')
        mean, std = list(training['mean']), list(training['std'])
    else:
        mean, std = [0.] * 3, [1.] * 3
    for source, target in enumerate(rgb):
        mean[target], std[target] = info['mean'][source], info['std'][source]
    return {'mean': mean, 'std': std, 'fitted_on': 'pretrained_rgb_train_extras', 'weight_id': info['weight_id']}


def build_candidate(candidate, spec, weights_path, receipt, head_only=False):
    """Load a locally reviewed tensor checkpoint; never retrieve or execute Hub code."""
    import hashlib
    from pathlib import Path
    from torchvision.models import mobilenet_v3_small
    from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large
    info = candidate_info(candidate, spec)
    if head_only and spec['channels'] != 3:
        raise ValueError('Adapted extra channels need fine-tuning, not a frozen backbone')
    path = Path(weights_path)
    if (receipt.get('url') != info['url'] or receipt.get('weight_id') != info['weight_id']
            or receipt.get('terms_reviewed') is not True or receipt.get('target_finetuned') is not False
            or receipt.get('heldout_overlap') not in ('none_known', 'unknown_recorded')):
        raise ValueError('Unreviewed, incompatible or contaminated checkpoint')
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
        raise ValueError('Weight checksum mismatch')
    state = torch.load(path, map_location='cpu', weights_only=True)
    if candidate == 'resnet18_imagenet':
        model = resnet18(weights=None)
        model.load_state_dict(state, strict=True)
        model.fc = torch.nn.Linear(model.fc.in_features, spec['classes'])
        stem, key = model, 'conv1'
        head = model.fc
    elif candidate == 'mobilenet_small_imagenet':
        model = mobilenet_v3_small(weights=None)
        model.load_state_dict(state, strict=True)
        model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, spec['classes'])
        stem, key, head = model.features[0], '0', model.classifier
    elif candidate == 'fcn_imagenet':
        model = fcn_resnet50(weights=None, weights_backbone=None, num_classes=spec['classes'], aux_loss=False)
        model.backbone.load_state_dict({k:v for k,v in state.items() if not k.startswith('fc.')}, strict=True)
        stem, key, head = model.backbone, 'conv1', model.classifier
    else:
        model = deeplabv3_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=spec['classes'], aux_loss=False)
        model.backbone.load_state_dict({k[len('features.'):]:v for k,v in state.items() if k.startswith('features.')}, strict=True)
        stem, key, head = model.backbone['0'], '0', model.classifier
    old = getattr(stem, key)
    if spec['channels'] != 3 or spec['rgb_indices'] != [0, 1, 2]:
        replacement = torch.nn.Conv2d(spec['channels'], old.out_channels, old.kernel_size,
                                      old.stride, old.padding, bias=False)
        with torch.no_grad():
            for source, target in enumerate(spec['rgb_indices']):
                replacement.weight[:, target].copy_(old.weight[:, source])
        setattr(stem, key, replacement)
    if head_only:
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        for parameter in head.parameters():
            parameter.requires_grad_(True)
    model.gotrain_weight_receipt = {**receipt, **info, 'head_only': head_only}
    return model


def set_training_mode(model, freeze_batchnorm=True):
    """Call at each epoch; head-only backbones also keep dropout disabled."""
    model.train()
    if model.gotrain_weight_receipt['head_only']:
        model.eval()
        head = model.fc if hasattr(model, 'fc') else model.classifier
        head.train()
    if freeze_batchnorm:
        for module in model.modules():
            if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
                module.eval()
