"""YOLO-only adapter around the retained DeviationLab inference code."""
import importlib.util
from dataclasses import dataclass
import math
import re
from typing import Callable
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
ASSETS = Path(os.environ.get('DEVIATIONLAB_ASSETS', ROOT / 'engine-assets'))
VENDOR = Path(os.environ.get('DEVIATIONLAB_VENDOR', ROOT / 'vendor'))
TARGETS = {'kitchen': ['cap_absent', 'mask_uncovered', 'uniform_absent'],
           'front': ['table_uncleared', 'bread_shelf_underfilled', 'cashier_vacancy']}
LABELS = {'cap_absent': 'Missing cap or hairnet',
          'mask_uncovered': 'Mask not covering nose and mouth',
          'uniform_absent': 'Missing workwear or apron',
          'table_uncleared': 'Uncleared table',
          'bread_shelf_underfilled': 'Underfilled bread display',
          'cashier_vacancy': 'Unattended cashier station'}
_yolo = None


def _yolo_availability():
    from two_stage import ready
    return ready()


@dataclass(frozen=True)
class EngineSpec:
    """Trusted server-side registration; callbacks and credentials are never published."""
    id: str
    label_en: str
    label_zh: str
    protocol: str
    check_ready: Callable
    external: bool  # Required: each adapter explicitly declares its data flow.
    input_mode: str = 'image'  # image: per sample; frames/video: one call per job.
    targets: tuple = tuple(LABELS)
    media_types: tuple = ('image', 'video')
    image_infer: Callable | None = None
    sequence_infer: Callable | None = None
    supports_boxes: bool = False
    cashier_roi_required: bool = False
    sends_reference_images: bool = False
    daily_limit_env: str | None = None
    default_daily_limit: int = 20

    def public(self):
        return {'id': self.id, 'label': {'en': self.label_en, 'zh': self.label_zh},
                'protocol': self.protocol, 'external': self.external,
                'requires_consent': self.external, 'input_mode': self.input_mode,
                'targets': list(self.targets), 'media_types': list(self.media_types),
                'scenes': [scene for scene, targets in TARGETS.items() if set(targets) & set(self.targets)],
                'supports_boxes': self.supports_boxes, 'cashier_roi_required': self.cashier_roi_required,
                'sends_reference_images': self.sends_reference_images}


@dataclass(frozen=True)
class SequenceInput:
    """Paths are private temporary files, valid only during the adapter call."""
    source: Path
    samples: tuple  # Ordered (timestamp_s, decoded_image_path) pairs.
    duration_s: float
    media_kind: str
    scene: str
    roi: tuple | None


REGISTRY_VERSION = 'proposal-two-stage-001'
_REGISTRY = {}


def register(spec):
    if (not isinstance(spec, EngineSpec) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', spec.id)
            or spec.id in _REGISTRY):
        raise ValueError('Invalid or duplicate engine registration')
    if (spec.input_mode not in ('image', 'frames', 'video') or type(spec.external) is not bool
            or not isinstance(spec.targets, tuple) or not spec.targets
            or len(set(spec.targets)) != len(spec.targets) or set(spec.targets) - set(LABELS)
            or not isinstance(spec.media_types, tuple) or not spec.media_types
            or set(spec.media_types) - {'image', 'video'}
            or not callable(spec.check_ready)
            or not all(isinstance(v, str) and 0 < len(v) <= 256
                       for v in (spec.label_en, spec.label_zh, spec.protocol))
            or any(type(flag) is not bool for flag in (spec.supports_boxes, spec.cashier_roi_required, spec.sends_reference_images))
            or type(spec.default_daily_limit) is not int or spec.default_daily_limit < 1):
        raise ValueError('Invalid engine capabilities')
    if spec.input_mode == 'image':
        if not callable(spec.image_infer) or spec.sequence_infer is not None:
            raise ValueError('Image engines require image_infer only')
    elif not callable(spec.sequence_infer) or spec.image_infer is not None:
        raise ValueError('Sequence engines require sequence_infer only')
    if spec.input_mode == 'video' and spec.media_types != ('video',):
        raise ValueError('Native video adapters must declare video-only media')
    _REGISTRY[spec.id] = spec


def get_engine(engine):
    if not isinstance(engine, str) or engine not in _REGISTRY:
        raise ValueError('Choose a registered engine')
    return _REGISTRY[engine]


def scope(engine, scene):
    spec = get_engine(engine)
    targets = [target for target in TARGETS.get(scene, ()) if target in spec.targets]
    if not targets:
        raise ValueError('Selected engine does not support this scene')
    return targets


def availability():
    status = {}
    for name, spec in _REGISTRY.items():
        try:
            ready = spec.check_ready()
            # Only explicit public booleans; never forward arbitrary provider configuration.
            public_ready = {key: ready.get(key) is True for key in ('available', 'configured', 'assets_ready')}
        except Exception:
            public_ready = {'available': False, 'configured': False, 'assets_ready': False}
        status[name] = {**spec.public(), **public_ready}
    return status


def yolo_image(image, scene, roi):
    from two_stage import analyze
    return analyze(image, scene, roi)


def _validate_prediction(result, engine, scene):
    spec = get_engine(engine)
    if (not isinstance(result, dict) or result.get('protocol') != spec.protocol
            or not isinstance(result.get('provider_model'), str)
            or not 0 < len(result['provider_model']) <= 256
            or not isinstance(result.get('assessments'), list)):
        raise ValueError('Invalid adapter result header')
    expected = set(scope(engine, scene))
    rows = result['assessments']
    if (len(rows) != len(expected) or any(not isinstance(row, dict) for row in rows)
            or {row.get('type') for row in rows} != expected):
        raise ValueError('Adapter must return exactly the declared scene targets')
    for row in rows:
        execution = row.get('execution_status', 'completed')
        if (row.get('status') not in ('present', 'absent', 'uncertain', 'not_applicable')
                or execution not in ('completed', 'configuration_required', 'unavailable', 'failed', 'not_run')
                or (execution != 'completed' and row['status'] != 'not_applicable')
                or not isinstance(row.get('evidence'), str) or not 0 < len(row['evidence']) <= 3000):
            raise ValueError('Invalid assessment')
        score = row.get('score')
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError('Invalid assessment score')
        boxes = row.get('boxes_1000', [])
        if not isinstance(boxes, list) or len(boxes) > 100:
            raise ValueError('Invalid evidence boxes')
        boxes = boxes + ([row['bbox_1000']] if row.get('bbox_1000') is not None else [])
        for box in boxes:
            if (not isinstance(box, list) or len(box) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1000 for v in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError('Invalid evidence box')
    return result


def _require_ready(engine, scene):
    scope(engine, scene)
    if not availability()[engine]['available']:
        raise ValueError(f'{engine} is not installed/configured. No substitute model was used.')


def infer(image, scene, engine, roi=None):
    spec = get_engine(engine)
    _require_ready(engine, scene)
    if spec.input_mode != 'image':
        raise ValueError('Sequence adapters must use analyze_samples')
    try:
        return _validate_prediction(spec.image_infer(image, scene, roi), engine, scene)
    except Exception as error:
        # Never echo a provider response body, credential, or arbitrary adapter error.
        raise ValueError(f'{engine} inference failed ({type(error).__name__}); no substitute model was used.') from None


def analyze_samples(source, frames, duration, scene, engine, roi=None):
    """Yield validated frame results; sequence models map evidence to requested sample indices.

    Native video adapters receive the original media too. They currently return
    sampled assessments, not tracker-verified intervals or continuous events.
    """
    spec = get_engine(engine)
    scope(engine, scene)
    if not frames:
        raise ValueError('No evidence samples')
    kind = 'video' if duration > 0 else 'image'
    if kind not in spec.media_types:
        raise ValueError('Selected engine does not support this media type')
    if spec.input_mode == 'image':
        for index, (timestamp, image) in enumerate(frames):
            yield index, timestamp, infer(image, scene, engine, roi)
        return
    _require_ready(engine, scene)
    context = SequenceInput(Path(source), tuple(frames), duration, kind, scene, tuple(roi) if roi else None)
    try:
        results = spec.sequence_infer(context)
        if (not isinstance(results, list) or len(results) != len(frames)
                or any(not isinstance(row, dict) or type(row.get('frame_index')) is not int for row in results)
                or {row['frame_index'] for row in results} != set(range(len(frames)))):
            raise ValueError('Sequence results must cover each requested sample index exactly once')
        ordered = sorted(results, key=lambda row: row['frame_index'])
        for result in ordered:
            _validate_prediction(result, engine, scene)
        if len({result['provider_model'] for result in ordered}) != 1:
            raise ValueError('Sequence results must identify one model version')
    except Exception as error:
        raise ValueError(f'{engine} inference failed ({type(error).__name__}); no substitute model was used.') from None
    for index, result in enumerate(ordered):
        yield index, frames[index][0], result


def events_from_frame(result, timestamp, frame_index):
    events = []
    for row in result['assessments']:
        if row.get('execution_status', 'completed') != 'completed' or row['status'] not in ('present', 'uncertain'):
            continue
        boxes = row.get('boxes_1000') or ([row['bbox_1000']] if row.get('bbox_1000') else [])
        events.append({'start_s': timestamp, 'end_s': timestamp,
                       'behavior': LABELS[row['type']], 'deviation_type': row['type'],
                       'status': 'observed' if row['status'] == 'present' else 'uncertain',
                       'evidence': row['evidence'], 'bbox_1000': boxes[0] if boxes else None,
                       'boxes_1000': boxes, 'frame_index': frame_index})
    return events


def summarize_events(events):
    """Group by category/status, retaining sample evidence without tracking claims."""
    groups = {}
    for event in events:
        key = (event['deviation_type'], event['status'])
        if key not in groups:
            groups[key] = {**event, 'observations': []}
        groups[key]['observations'].append(dict(event))
    for group in groups.values():
        observations = group['observations']
        group['sample_count'] = len(observations)
        group['sample_times_s'] = [row['start_s'] for row in observations]
    return list(groups.values())


# Lazy callbacks keep retained model code isolated and avoid loading weights on status checks.
register(EngineSpec(id='yolo', label_en='YOLO + MobileNetV3', label_zh='YOLO',
    protocol='proposal-two-stage-001', check_ready=_yolo_availability, external=False,
    image_infer=lambda image, scene, roi: yolo_image(image, scene, roi),
    supports_boxes=True, cashier_roi_required=True))
