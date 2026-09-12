"""Small release-tree consistency check; no network access."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'custom_components/lotto_645/manifest.json').read_text())
assert {'frontend', 'http', 'panel_custom', 'websocket_api'} <= set(manifest['dependencies'])
assert (root / 'scripts/smoke_ticket_panel.py').is_file()
assert not (root / 'scripts/test_ticket_panel.py').exists()
assert 'patch.object(hass, \'config_entries\'' in (root / 'scripts/smoke_ha_options.py').read_text()
print('Resumed runtime tree is consistent')
