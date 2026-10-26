import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parents[1]))
import server as s
import engines


class FrameTests(unittest.TestCase):
    def test_events_validated_and_box_retained(self):
        row = {'start_s': 0, 'end_s': 0, 'behavior': 'mask', 'status': 'observed',
               'evidence': 'visible uncovered nose', 'bbox_1000': [100, 100, 300, 300]}
        self.assertEqual(s.validate_result({'events': [row]}, 0)['events'][0]['bbox_1000'], row['bbox_1000'])

    def test_bad_times(self):
        for start, end in [(float('nan'), 1), (1, 11), (2, 1), (-1, 0)]:
            with self.assertRaises(ValueError):
                s.validate_result({'events': [{'start_s': start, 'end_s': end,
                    'behavior': 'x', 'evidence': 'x', 'status': 'observed'}]}, 10)

    def test_invalid_roi(self):
        for roi in [[0, 0, 2, 1], [1, 1, 0, 0], [True, 0, 1, 1], [float('nan'), 0, 1, 1]]:
            with self.assertRaises(ValueError):
                s.validate_roi(roi)

    def test_real_video_extract_native_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'test.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=1200x200:rate=3',
                            '-t', '2', '-pix_fmt', 'yuv420p', str(source)], check=True, capture_output=True)
            duration, frames = s.extract_frames(source, Path(folder), 3)
            self.assertAlmostEqual(duration, 2, places=1)
            self.assertEqual(len(frames), 3)
            from PIL import Image
            with Image.open(frames[0][1]) as image:
                self.assertEqual(image.size, (1200, 200))

    def test_image_one_frame(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.png'
            Image.new('RGB', (64, 64), 'red').save(source)
            duration, frames = s.extract_frames(source, Path(folder), 12)
            self.assertEqual(duration, 0)
            self.assertEqual(len(frames), 1)

    def test_pipeline_original_predictions_retained(self):
        result = {'assessments': [{'type': 'mask_uncovered', 'status': 'present',
                   'evidence': 'fixture', 'bbox_1000': [10, 20, 100, 200]}],
                  'provider_model': 'original-test', 'protocol': 'original-protocol'}
        with tempfile.TemporaryDirectory() as folder, patch.object(s, 'DATA', Path(folder)):
            path = Path(folder) / 'jobs' / ('a' * 32 + '.json')
            s.write_record(path, {'review_history': [], 'state': 'queued'})
            with patch.object(s, 'extract_frames', return_value=(2, [(0, Path('frame.png')), (1, Path('frame2.png'))])), \
                 patch.object(engines, 'infer', return_value=result) as infer:
                s.process('a' * 32, b'test', 'context', 'kitchen', 'yolo')
            record = json.loads(path.read_text())
            self.assertEqual(record['state'], 'completed')
            self.assertEqual(len(record['events']), 1)
            self.assertEqual(len(record['frame_events']), 2)
            self.assertEqual(record['events'][0]['sample_times_s'], [0, 1])
            self.assertEqual(len(record['frame_results']), 2)
            self.assertTrue(all(call.args[2] == 'yolo' for call in infer.call_args_list))
            self.assertEqual(record['events'][0]['observations'][1]['start_s'], 1)
            reviewed = s.validate_result({'events': record['events']}, 2)
            self.assertEqual(reviewed['events'][0]['sample_times_s'], [0, 1])

    def test_summary_separates_category_and_uncertainty(self):
        def event(kind, status, time):
            return {'deviation_type': kind, 'status': status, 'start_s': time,
                    'end_s': time, 'behavior': kind, 'evidence': str(time)}
        raw = [event('mask_uncovered', 'observed', 0),
               event('mask_uncovered', 'uncertain', 1),
               event('mask_uncovered', 'observed', 3),
               event('cap_absent', 'observed', 3)]
        result = engines.summarize_events(raw)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['sample_times_s'], [0, 3])
        self.assertEqual(result[0]['end_s'], 0)  # No inferred continuous duration.
        self.assertNotIn('observations', raw[0])
        self.assertEqual(engines.summarize_events([]), [])
        self.assertEqual(engines.summarize_events(raw[:1])[0]['sample_count'], 1)

    def test_only_yolo_is_registered(self):
        self.assertEqual(set(engines.availability()), {'yolo'})
        with self.assertRaisesRegex(ValueError, 'registered engine'):
            engines.get_engine('qwen')
        with self.assertRaisesRegex(ValueError, 'registered engine'):
            engines.get_engine('deepseek')

    def test_not_completed_never_becomes_normal_or_issue(self):
        result = {'assessments': [{'type': 'cashier_vacancy', 'status': 'not_applicable',
                  'execution_status': 'configuration_required', 'evidence': 'ROI required'}]}
        self.assertEqual(engines.events_from_frame(result, 0, 0), [])

    def test_same_class_multiple_boxes_grouped_per_frame(self):
        boxes = [[1, 1, 100, 100], [200, 200, 300, 300]]
        rows = engines.events_from_frame({'assessments':[{'type':'mask_uncovered',
            'status':'present','evidence':'two uncovered faces','boxes_1000':boxes}]},0,0)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['boxes_1000'],boxes)
        self.assertEqual(s.validate_result({'events':rows},0)['events'][0]['boxes_1000'],boxes)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = s.ThreadingHTTPServer(('127.0.0.1', 0), s.Handler)
        cls.url = f'http://127.0.0.1:{cls.http.server_port}'
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close()

    def post(self, value, endpoint='/api/analyze', headers=None):
        return urlopen(Request(self.url + endpoint, data=json.dumps(value).encode(),
                       headers={'Content-Type': 'application/json', **(headers or {})}))

    def test_status_yolo_only_no_secret(self):
        with urlopen(self.url + '/api/status') as response:
            value = json.load(response)
        self.assertEqual(set(value['engines']), {'yolo'})
        self.assertFalse(value['api_configured'])
        self.assertEqual(value['scenes'], ['kitchen', 'front'])
        self.assertNotIn('VLM_API_KEY', json.dumps(value))

    def test_home(self):
        with urlopen(self.url) as response:
            page = response.read()
            self.assertIn(b'YOLO', page)
            self.assertNotIn(b'id="engine"', page)
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])

    def test_private_assets_not_served(self):
        for path in ['/engine-assets/qwen/examples.json', '/vendor/qwen/qwen_api.py', '/engines.py',
                     '/run/deviationlab/config.json', '/api/jobs/../../server.py']:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

    def test_bad_host(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url, headers={'Host': 'evil.example'}))
        self.assertEqual(error.exception.code, 403)

    def test_cross_origin(self):
        with self.assertRaises(HTTPError) as error:
            self.post({}, headers={'Origin': 'https://evil.example'})
        self.assertEqual(error.exception.code, 403)

    def test_password(self):
        with patch.object(s, 'PASSWORD', 'fixture-only'):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url)
            self.assertEqual(error.exception.code, 401)

    def test_invalid_scope_and_json(self):
        for body in [[], {'engine': 'custom', 'scene': 'kitchen'}, {'engine': 'qwen', 'scene': 'kitchen'},
                     {'engine': 'deepseek', 'scene': 'kitchen'}, {'scene': 'sports'}]:
            with self.assertRaises(HTTPError) as error:
                self.post(body)
            self.assertEqual(error.exception.code, 400)

    def test_analysis_defaults_to_yolo_without_model_or_consent_fields(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'DATA', Path(temp)), \
             patch.object(engines, 'availability', return_value={'yolo': {'available': True}}), \
             patch.object(s, 'process'):
            with self.post({'scene': 'kitchen', 'media_base64': 'eA=='}) as response:
                self.assertEqual(response.status, 202)

    def test_review_append_only(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'DATA', Path(temp)):
            path = Path(temp) / 'jobs' / ('a'*32+'.json')
            s.write_record(path, {'state': 'completed', 'duration_s': 4,
                'events': [{'original': True}], 'review_history': []})
            for count in (1, 2):
                with self.post({'id': 'a'*32, 'result': {'events': []}, 'notes': 'checked'}, '/api/review') as response:
                    self.assertEqual(json.load(response)['review_count'], count)
            self.assertEqual(json.loads(path.read_text())['events'], [{'original': True}])


if __name__ == '__main__':
    unittest.main()
