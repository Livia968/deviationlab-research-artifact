"""Check a complete release without installing inference dependencies."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    checked = 0
    for line in (ROOT / 'SHA256SUMS.txt').read_text().splitlines():
        expected, name = line.split('  ', 1)
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SystemExit(f'Missing or invalid release file: {name}')
        if digest(path) != expected:
            raise SystemExit(f'Changed release file: {name}')
        checked += 1
    model_root = ROOT / 'proposal-pipeline/models'
    registry = json.loads((model_root / 'registry.json').read_text())
    summary = json.loads((model_root / 'training-summary.json').read_text())
    assert len(registry['targets']) == 6
    for name, spec in registry['targets'].items():
        assert digest(model_root / spec['weights']) == spec['weights_sha256'], name
        card = json.loads((model_root / name / 'model-card.json').read_text())
        for metric in ('accuracy', 'balanced_accuracy'):
            value = summary['models'][name]['development_' + metric]
            assert abs(card['validation'][metric] - value) < 1e-12, (name, metric)
            assert f'{value*100:.2f}%' in (ROOT / 'MODEL-STATUS.md').read_text()
    locators = json.loads((ROOT / 'localizers/registry.json').read_text())
    assert set(locators) == {'head', 'general', 'bread'}
    for spec in locators.values():
        assert digest(ROOT / 'localizers' / spec['file']) == spec['sha256']
    samples = json.loads((ROOT / 'samples/manifest.json').read_text())
    assert len(samples) == 11
    assert len({row['file'] for row in samples}) == len(samples)
    media = {p.name for p in (ROOT / 'samples').iterdir()
             if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.mp4', '.mov')}
    assert media == {row['file'] for row in samples}
    assert all(Path(row['file']).name == row['file'] for row in samples)
    assert sum(row['file'].endswith('.png') for row in samples) == 10
    assert sum(row['file'].endswith('.mp4') for row in samples) == 1
    for row in samples:
        assert digest(ROOT / 'samples' / row['file']) == row['sha256']
    report = json.loads((ROOT / 'functional-audit.json').read_text())
    assert report['status'] == 'pass' and len(report['cases']) == len(samples)
    cases = {row['file']: row for row in report['cases']}
    assert set(cases) == media
    for row in samples:
        assert cases[row['file']]['sha256'] == row['sha256']
        assert cases[row['file']]['state'] == 'completed' and cases[row['file']]['review_saved']
    print(f'PASS: {checked} file hashes, 6 classifiers, 3 localizers, 10 edited images, 1 reviewed video and saved development metrics.')
    print('This is an integrity check, not a recognition-accuracy test.')

if __name__ == '__main__':
    main()
