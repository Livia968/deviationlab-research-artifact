"""Authenticated YOLO workbench. The retained image workflow runs per sampled frame."""
import base64
import binascii
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import engines

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('BEHAVIORLENS_DATA', ROOT / 'workspace')).resolve()
MAX_BYTES = 30 * 1024 * 1024
WORKER = threading.Lock()
SAVE = threading.Lock()
PASSWORD = os.environ.get('BEHAVIORLENS_PASSWORD', '')
PROTOCOL = 'proposal-two-stage-web-001'


def write_record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def validate_roi(roi):
    if roi is None:
        return None
    if (not isinstance(roi, list) or len(roi) != 4 or
        any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in roi) or
        roi[0] >= roi[2] or roi[1] >= roi[3]):
        raise ValueError('ROI must be normalized x1,y1,x2,y2 within 0–1')
    return roi


def validate_result(value, duration):
    if not isinstance(value, dict) or not isinstance(value.get('events'), list) or len(value['events']) > 1200:
        raise ValueError('Invalid events array')
    events = []
    for event in value['events']:
        start, end = float(event['start_s']), float(event['end_s'])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration):
            raise ValueError('Event time outside clip')
        if event.get('status') not in ('observed', 'uncertain'):
            raise ValueError('Invalid evidence status')
        for name in ('behavior', 'evidence'):
            if not isinstance(event.get(name), str) or not event[name].strip() or len(event[name]) > 3000:
                raise ValueError('Missing event text')
        row = {k: event[k] for k in ('behavior', 'status', 'evidence')}
        row.update(start_s=start, end_s=end)
        if event.get('bbox_1000') is not None:
            row['bbox_1000'] = [v * 1000 for v in validate_roi([v / 1000 for v in event['bbox_1000']])]
        if event.get('boxes_1000') is not None:
            if not isinstance(event['boxes_1000'], list) or len(event['boxes_1000']) > 100:
                raise ValueError('Invalid boxes')
            row['boxes_1000'] = [[v * 1000 for v in validate_roi([v / 1000 for v in box])]
                                 for box in event['boxes_1000']]
        if event.get('deviation_type') in engines.LABELS:
            row['deviation_type'] = event['deviation_type']
        if type(event.get('frame_index')) is int and 0 <= event['frame_index'] < 12:
            row['frame_index'] = event['frame_index']
        if event.get('observations') is not None:
            observations = event['observations']
            if (not isinstance(observations, list) or not 1 <= len(observations) <= 12
                    or any(not isinstance(item, dict) or 'observations' in item for item in observations)):
                raise ValueError('Invalid sample observations')
            row['observations'] = validate_result({'events': observations}, duration)['events']
            row['sample_count'] = len(row['observations'])
            row['sample_times_s'] = [item['start_s'] for item in row['observations']]
        events.append(row)
    summary = value.get('summary', '')
    if not isinstance(summary, str) or len(summary) > 8000:
        raise ValueError('Invalid summary')
    return {'summary': summary, 'events': events}


def extract_frames(source, destination, count=6):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration',
        '-of', 'json', str(source)], check=True, capture_output=True, timeout=15)
    meta = json.loads(probe.stdout)
    stream = meta['streams'][0]
    width, height = int(stream['width']), int(stream['height'])
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise ValueError('Maximum dimensions: 4096 × 4096')
    raw = meta.get('format', {}).get('duration')
    duration = float(raw) if raw not in (None, 'N/A') else 0
    if not math.isfinite(duration) or not 0 <= duration <= 60.5:
        raise ValueError('Use a clip no longer than 60 seconds')
    if type(count) is not int or not 1 <= count <= 12:
        raise ValueError('Frame count must be 1–12')
    timestamps = [0.] if duration == 0 else [round(i * duration / count, 3) for i in range(count)]
    frames = []
    for i, timestamp in enumerate(timestamps):
        target = destination / f'frame-{i:02}.png'
        # Preserve native decoded pixels; retained pipelines apply their own resizing.
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-threads', '1', '-protocol_whitelist',
            'file,pipe', '-ss', str(timestamp), '-i', str(source), '-frames:v', '1', '-y', str(target)],
            check=True, capture_output=True, timeout=20)
        if target.exists() and target.stat().st_size:
            frames.append((timestamp, target))
    if not frames:
        raise ValueError('No decodable frames')
    return duration, frames


def process(job_id, media, prompt, scene, engine='yolo', roi=None, count=6):
    path = DATA / 'jobs' / (job_id + '.json')
    with WORKER:
        record = json.loads(path.read_text())
        try:
            record.update(state='running', frame_results=[], events=[])
            with SAVE:
                write_record(path, record)
            with tempfile.TemporaryDirectory(prefix='deviationlab-') as folder:
                directory = Path(folder)
                source = directory / 'upload'
                source.write_bytes(media)
                duration, frames = extract_frames(source, directory, count)
                record.update(duration_s=duration, sampled_timestamps_s=[t for t, _ in frames])
                record['engine_capabilities'] = engines.get_engine(engine).public()
                for index, timestamp, result in engines.analyze_samples(source, frames, duration, scene, engine, roi):
                    record['frame_results'].append({**result, 'timestamp_s': timestamp, 'frame_index': index})
                    record['events'].extend(engines.events_from_frame(result, timestamp, index))
                    record.update(progress={'completed_frames': index + 1, 'total_frames': len(frames)})
                    with SAVE:
                        write_record(path, record)
            record['frame_events'] = record['events']
            record['events'] = engines.summarize_events(record['frame_events'])
            record['aggregation_version'] = 'category-samples-001'
            observed = sum(e['status'] == 'observed' for e in record['events'])
            uncertain = sum(e['status'] == 'uncertain' for e in record['events'])
            not_run = sum(r.get('execution_status', 'completed') != 'completed'
                          for f in record['frame_results'] for r in f['assessments'])
            record.update(state='completed', provider_model=result['provider_model'],
                engine_protocol=result['protocol'], completed_at=time.time(),
                summary=f'{observed} issue categories · {uncertain} uncertain categories · {not_run} checks not completed. '
                        'Repeated samples are grouped by category; sample counts are not people or incident counts.')
        except Exception as error:
            record.update(state='failed', error=str(error) if isinstance(error, ValueError)
                          else 'Media processing failed; no substitute engine was used.')
        with SAVE:
            write_record(path, record)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, data, content_type='application/json'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type == 'application/json' else data
        self.send_response(code)
        for name, value in {'Content-Type': content_type, 'Content-Length': str(len(body)),
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'Content-Security-Policy':
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'"}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        if urlsplit('http://' + self.headers.get('Host', '')).hostname not in ('127.0.0.1', 'localhost', '::1'):
            self.reply(403, {'error': 'Use the authenticated HTTPS gateway'})
            return False
        if PASSWORD:
            expected = 'Basic ' + base64.b64encode(('research:' + PASSWORD).encode()).decode()
            if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="DeviationLab"')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path in ('/', '/app.js', '/i18n.js', '/dual.js', '/style.css', '/studio.css', '/workspace.css'):
            file = ROOT / 'static' / ('index.html' if path == '/' else path[1:])
            kind = 'text/html; charset=utf-8' if path == '/' else ('text/javascript' if path.endswith('.js') else 'text/css')
            return self.reply(200, file.read_bytes(), kind)
        if path == '/api/status':
            status = engines.availability()
            return self.reply(200, {'api_configured': False,
                'model': 'YOLO + MobileNetV3', 'mode': 'sampled-frame analysis',
                'max_seconds': 60, 'protocol': PROTOCOL, 'scenes': list(engines.TARGETS), 'scene_targets': engines.TARGETS,
                'engines': status, 'registry_version': engines.REGISTRY_VERSION,
                'target_labels': {key: {'en': label} for key, label in engines.LABELS.items()},
                'default_frames': 6, 'max_frames': 12,
                'configuration_is_not_connectivity_test': True})
        if path.startswith('/api/jobs/'):
            job = path.rsplit('/', 1)[-1]
            if len(job) == 32 and all(c in '0123456789abcdef' for c in job):
                file = DATA / 'jobs' / (job + '.json')
                if file.is_file():
                    with SAVE:
                        return self.reply(200, json.loads(file.read_text()))
        self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.allowed():
            return
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
            return self.reply(403, {'error': 'Cross-origin requests blocked'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'JSON required'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BYTES * 4 // 3 + 20000:
                return self.reply(413, {'error': 'Maximum upload: 30MB'})
            self.connection.settimeout(45)
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError('JSON object required')
            if self.path == '/api/analyze':
                requested_engine, scene = value.get('engine', 'yolo'), value.get('scene')
                if requested_engine != 'yolo':
                    return self.reply(400, {'error': 'This site only supports its local YOLO workflow.'})
                engine = 'yolo'
                spec = engines.get_engine(engine)
                engines.scope(engine, scene)
                if not engines.availability()[engine]['available']:
                    return self.reply(409, {'error': 'Selected engine is not ready. No substitute model will be used.'})
                roi = validate_roi(value.get('cashier_roi'))
                count = value.get('sample_count', 6)
                if type(count) is not int or not 1 <= count <= 12:
                    raise ValueError('Invalid sample count')
                prompt = value.get('prompt', '')
                if not isinstance(prompt, str) or len(prompt) > 4000:
                    raise ValueError('Invalid note')
                media = base64.b64decode(value.get('media_base64', ''), validate=True)
                if not 0 < len(media) <= MAX_BYTES:
                    raise ValueError('Maximum upload: 30MB')
                with SAVE:
                    records = [json.loads(p.read_text()) for p in (DATA / 'jobs').glob('*.json')]
                    if sum(r.get('state') in ('queued', 'running') for r in records) >= 2:
                        return self.reply(429, {'error': 'Queue full. Wait for the current analysis.'})
                    job = secrets.token_hex(16)
                    write_record(DATA / 'jobs' / (job + '.json'), {'id': job, 'state': 'queued',
                        'engine': engine, 'engine_capabilities': spec.public(), 'registry_version': engines.REGISTRY_VERSION,
                        'external_processing_consent': None,
                        'cashier_roi': roi, 'requested_frames': count,
                        'created_at': time.time(), 'scene': scene, 'task': prompt,
                        'task_policy': 'registered_adapter_workflow; task_text_is_context_not_prompt_override',
                        'source_sha256': hashlib.sha256(media).hexdigest(), 'protocol_version': PROTOCOL,
                        'review_history': [], 'limitation': 'Sampled image judgments, not continuous tracking or durations'})
                threading.Thread(target=process, args=(job, media, prompt, scene, engine, roi, count), daemon=True).start()
                return self.reply(202, {'id': job})
            if self.path == '/api/review':
                job = value.get('id', '')
                if len(job) != 32 or any(c not in '0123456789abcdef' for c in job):
                    raise ValueError('Invalid job')
                path = DATA / 'jobs' / (job + '.json')
                with SAVE:
                    record = json.loads(path.read_text())
                    if record['state'] != 'completed':
                        raise ValueError('Only completed analyses can be reviewed')
                    corrected = validate_result(value.get('result'), record['duration_s'])
                    notes = value.get('notes', '')
                    if not isinstance(notes, str) or len(notes) > 4000:
                        raise ValueError('Review notes too long')
                    record['review_history'].append({'at': time.time(), 'result': corrected, 'notes': notes})
                    write_record(path, record)
                return self.reply(200, {'saved': True, 'review_count': len(record['review_history'])})
            self.reply(404, {'error': 'Not found'})
        except (ValueError, KeyError, TypeError, binascii.Error, FileNotFoundError):
            self.reply(400, {'error': 'Invalid request. Check the scene, media, cashier region and timestamps.'})


if __name__ == '__main__':
    host = os.environ.get('BEHAVIORLENS_HOST', '127.0.0.1')
    if host != '127.0.0.1' and not PASSWORD:
        raise SystemExit('Non-loopback binding requires a website password.')
    DATA.mkdir(parents=True, exist_ok=True)
    for file in (DATA / 'jobs').glob('*.json'):
        record = json.loads(file.read_text())
        if record.get('state') in ('queued', 'running'):
            record.update(state='failed', error='Server restarted; no paid work was replayed.')
            write_record(file, record)
    port = int(os.environ.get('PORT', '7870'))
    print(f'DeviationLab: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
