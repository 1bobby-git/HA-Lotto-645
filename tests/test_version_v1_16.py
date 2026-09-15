from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_alignment():
    root = ROOT / 'custom_components/lotto_645'
    version = json.loads((root / 'manifest.json').read_text())['version']
    assert tuple(map(int, version.split('.'))) >= (1, 16, 0)
    assert f'VERSION = "{version}"' in (root / 'const.py').read_text()
    shell = (root / 'www/lotto-panel-shell.js').read_text()
    assert f"data-lotto-ha-host-header', '{version}'" in shell
    assert f'lotto-panel-validation.js?v={version}' in shell
    validation = (root / 'www/lotto-panel-validation.js').read_text()
    assert f"VALIDATION_UI_VERSION = '{version}'" in validation
