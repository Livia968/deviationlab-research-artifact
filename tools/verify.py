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
    assert len(list((ROOT / 'samples').glob('*.mp4'))) == 6
    assert len(list((ROOT / 'samples').glob('*.jpg'))) == 6
    for row in json.loads((ROOT / 'samples/manifest.json').read_text()):
        assert digest(ROOT / 'samples' / row['file']) == row['sha256']
    report = json.loads((ROOT / 'functional-audit.json').read_text())
    assert report['status'] == 'pass' and len(report['cases']) == 12
    print(f'PASS: {checked} file hashes, 6 classifiers, 3 localizers, 12 sample files and saved development metrics.')
    print('This is an integrity check, not a recognition-accuracy test.')

if __name__ == '__main__':
    main()
