"""Run the 12 private walkthrough cases against a local reviewer server."""
import argparse
import base64
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirects are disabled for private sample testing')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7891')
    args = parser.parse_args()
    parts = urlsplit(args.url)
    if parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost') or parts.username or parts.password or parts.query:
        parser.error('Use a local HTTP server; this test must not transmit the private samples to an external host.')
    base = args.url.rstrip('/')
    opener = build_opener(NoRedirect())
    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(base + path, data=data, headers={'Content-Type':'application/json'})
        with opener.open(req, timeout=30) as response:
            if urlsplit(response.url).hostname not in ('127.0.0.1', 'localhost'):
                raise RuntimeError('Unexpected server redirect')
            return json.load(response)
    status = request('/api/status')
    assert status['engines']['yolo']['available'], 'Local engine is unavailable'
    cases = []
    for sample in json.loads((ROOT / 'samples/manifest.json').read_text()):
        for extension in ('.jpg', '.mp4'):
            path = (ROOT / 'samples' / sample['file']).with_suffix(extension)
            payload = {'media_base64':base64.b64encode(path.read_bytes()).decode(),
                       'scene':sample['scene'], 'sample_count':3, 'engine':'yolo'}
            if path.stem == 'front-cashier':
                payload['cashier_roi'] = [.1,.1,.9,.9]
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
            assert len(frames) == (3 if extension == '.mp4' else 1)
            assert all(len(frame['assessments']) == 3 for frame in frames)
            assert all(frame['provider_model'] == 'mobilenetv3-roi-v2' for frame in frames)
            assert all(row['execution_status'] in ('completed','configuration_required') for frame in frames for row in frame['assessments'])
            saved = request('/api/review', {'id':job['id'], 'result':{'summary':record['summary'], 'events':record['events']}, 'notes':'Automated functional check; not an accuracy label.'})
            assert saved['saved']
            case = {'file':path.name, 'state':record['state'], 'frames':len(frames),
                    'seconds':round(time.monotonic()-started,2), 'review_saved':True,
                    'statuses':[{row['type']:row['status'] for row in frame['assessments']} for frame in frames]}
            cases.append(case)
            print(json.dumps(case), flush=True)
    print(json.dumps({'status':'pass', 'scope':'functional integration, not accuracy validation',
                      'cases':cases, 'model':'mobilenetv3-roi-v2',
                      'cashier_test_roi':'arbitrary central geometry for functional test only'}), flush=True)

if __name__ == '__main__':
    main()
