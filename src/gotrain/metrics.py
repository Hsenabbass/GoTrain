"""Frozen global-confusion-matrix metrics; independent of model recipes."""
import torch


class Confusion:
    def __init__(self, classes, ignore_target=None, exclude_macro=()):
        self.classes, self.ignore_target, self.exclude_macro = classes, ignore_target, exclude_macro
        self.matrix = torch.zeros((classes, classes), dtype=torch.int64)

    def update(self, prediction, target):
        if prediction.shape != target.shape or prediction.dtype != torch.long or target.dtype != torch.long:
            raise ValueError('Metric expects matching int64 class-ID tensors')
        p, y = prediction.detach().cpu().flatten(), target.detach().cpu().flatten()
        if ((p < 0) | (p >= self.classes)).any() or ((y < 0) | (y >= self.classes)).any():
            raise ValueError('Metric class ID out of range')
        if self.ignore_target is not None:
            keep = y != self.ignore_target
            p, y = p[keep], y[keep]
        self.matrix += torch.bincount(y * self.classes + p, minlength=self.classes**2).reshape(self.classes, self.classes)

    def compute(self, allow_empty=False):
        m = self.matrix.double()
        if not m.sum():
            if allow_empty:
                return {'count': 0, 'macro_iou': None, 'valid': False}
            raise ValueError('Empty evaluation is invalid')
        tp, support, predicted = m.diag(), m.sum(1), m.sum(0)
        union = support + predicted - tp
        divide = lambda a, b: torch.where(b > 0, a / b.clamp_min(1), torch.zeros_like(a))
        iou, precision, recall = divide(tp, union), divide(tp, predicted), divide(tp, support)
        f1 = divide(2 * tp, support + predicted)
        included = union > 0
        for k in self.exclude_macro:
            included[k] = False
        return {'valid': bool(included.any()), 'count': int(m.sum()),
                'accuracy': float(tp.sum() / m.sum()),
                'macro_iou': float(iou[included].mean()) if included.any() else None,
                'macro_f1': float(f1.mean()), 'per_class_iou': iou.tolist(),
                'per_class_precision': precision.tolist(), 'per_class_recall': recall.tolist(),
                'per_class_f1': f1.tolist(), 'support': support.long().tolist(),
                'union': union.long().tolist(), 'confusion_matrix': self.matrix.tolist()}
