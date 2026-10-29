"""Test the manifest-listed demonstrations against a local reviewer server."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirects are disabled for sample testing')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7891')
    parser.add_argument('--report', type=Path, help='Optional JSON verification report; overwrites the specified file')
    args = parser.parse_args()
    parts = urlsplit(args.url)
    if (parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost')
            or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('','/')):
        parser.error('Use a local HTTP server; media must not be sent to an external host.')
    opener = build_opener(NoRedirect())
    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(args.url.rstrip('/') + path, data=data, headers={'Content-Type':'application/json'})
        with opener.open(req, timeout=120) as response:
            return json.load(response)
    status = request('/api/status')
    assert status['engines']['yolo']['available'] and status['protocol'] == 'proposal-two-stage-web-001'
    cases = []
    for sample in json.loads((ROOT / 'samples/manifest.json').read_text()):
        assert Path(sample['file']).name == sample['file']
        path = ROOT / 'samples' / sample['file']
        media = path.read_bytes()
        digest = hashlib.sha256(media).hexdigest()
        assert digest == sample['sha256'], path.name
        count = 3 if path.suffix.lower() in ('.mp4', '.mov') else 1
        payload = {'media_base64':base64.b64encode(media).decode(),
                   'scene':sample['scene'], 'sample_count':count, 'engine':'yolo'}
        if sample.get('cashier_roi') is not None:
            payload['cashier_roi'] = sample['cashier_roi']
        started = time.monotonic()
        job = request('/api/analyze', payload)
        while True:
            record = request('/api/jobs/' + job['id'])
            if record['state'] in ('completed', 'failed'):
                break
            if time.monotonic() - started > 600:
                raise TimeoutError(f'{path.name}: analysis exceeded ten minutes')
            time.sleep(.5)
        assert record['state'] == 'completed', (path.name, record.get('error'))
        frames = record['frame_results']
        assert len(frames) == count
        assert all(len(frame['assessments']) == 3 for frame in frames)
        assert all(frame['provider_model'] == 'mobilenetv3-roi-v2' for frame in frames)
        assert all(row['execution_status'] in ('completed','configuration_required')
                   for frame in frames for row in frame['assessments'])
        saved = request('/api/review', {'id':job['id'], 'result':{'summary':record['summary'], 'events':record['events']},
                                      'notes':'Automated functional check; not an accuracy label.'})
        assert saved['saved'] and request('/api/jobs/' + job['id'])['review_history']
        predictions = [{row['type']:row['status'] for row in frame['assessments']} for frame in frames]
        case = {'file':path.name, 'sha256':digest, 'state':record['state'], 'frames':len(frames),
                'seconds':round(time.monotonic()-started,2), 'review_saved':True,
                'cashier_roi':sample.get('cashier_roi'), 'target':sample['target'],
                'visual_reference':sample['visual_reference'], 'statuses':predictions,
                'target_status':predictions[0][sample['target']]}
        cases.append(case)
        print(json.dumps(case), flush=True)
    report = {'status':'pass', 'scope':'functional integration, not accuracy validation',
              'tested_at_utc':datetime.now(timezone.utc).isoformat(), 'cases':cases,
              'model':'mobilenetv3-roi-v2', 'application_protocol':status['protocol'],
              'environment':{'python':platform.python_version(), 'system':platform.system(),
                 'machine':platform.machine(), 'dependencies':{n:version(n) for n in ('torch','torchvision','ultralytics','Pillow','numpy')}},
              'limitations':'Mask coverage has no suitable sample. Workwear reference 02 is uncertain. Crops were selected for readability and privacy, not prediction success. No new accuracy estimate.'}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)

if __name__ == '__main__':
    main()
