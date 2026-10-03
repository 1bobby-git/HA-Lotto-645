"""Executable frontend contract: passive updates must not rebuild a reading page."""
import shutil
import subprocess
import pytest


def test_manual_panel_refresh_contract():
    if not shutil.which('node'):
        pytest.skip('Node unavailable; manual refresh contract not run')
    result = subprocess.run(['node', 'tests/js/manual-panel-refresh.mjs'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
