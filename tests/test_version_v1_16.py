from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_v1_16_version_alignment():
    const = (ROOT / 'custom_components/lotto_645/const.py').read_text()
    manifest = json.loads((ROOT / 'custom_components/lotto_645/manifest.json').read_text())
    assert 'VERSION = "1.16.0"' in const
    assert manifest['version'] == '1.16.0'
