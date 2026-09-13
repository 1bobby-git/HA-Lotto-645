"""Actual HA frontend panel lifecycle; local mocked HTTP registration only."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import importlib

async def check_panel_lifecycle(hass):
    from homeassistant.components import frontend
    p=importlib.import_module('custom_components.lotto_645.ticket_panel')
    entries={'one': SimpleNamespace(entry_id='one',title='One',disabled_by=None),
             'two': SimpleNamespace(entry_id='two',title='Two',disabled_by=None)}
    http=SimpleNamespace(async_register_static_paths=AsyncMock())
    registry=SimpleNamespace(async_get_entry=lambda key:entries.get(key))
    with patch.object(hass,'http',http,create=True), patch.object(hass,'config_entries',registry), patch.object(p.websocket_api,'async_register_command',Mock()) as register:
        await asyncio.gather(*(p.async_register_ticket_panel(hass,entries['one']) for _ in range(2)))
        assert frontend.async_panel_exists(hass,p.PATH)
        assert http.async_register_static_paths.await_count==2 # web resources + brand, once each
        assert register.call_count==4
        p.async_remove_ticket_panel(hass,'one') # temporary options reload
        assert frontend.async_panel_exists(hass,p.PATH)
        await p.async_register_ticket_panel(hass,entries['one'])
        assert http.async_register_static_paths.await_count==2
        frontend.async_remove_panel(hass,p.PATH)
        p.async_ensure_ticket_panel(hass)
        assert frontend.async_panel_exists(hass,p.PATH)
        panel=hass.data[frontend.DATA_PANELS][p.PATH]
        assert panel.require_admin and panel.config['_panel_custom']['handle_safe_area']
        await p.async_register_ticket_panel(hass,entries['two'])
        p.async_remove_ticket_panel(hass,'one',permanent=True)
        assert set(hass.data[frontend.DATA_PANELS][p.PATH].config['entries'])=={'two'}
        entries['two'].disabled_by='user'
        p.async_remove_ticket_panel(hass,'two')
        assert not frontend.async_panel_exists(hass,p.PATH)
        entries['two'].disabled_by=None
        await p.async_register_ticket_panel(hass,entries['two'])
        assert frontend.async_panel_exists(hass,p.PATH)
        assert http.async_register_static_paths.await_count==2
        p.async_remove_ticket_panel(hass,'two',permanent=True)
    print('PASS: real HA panel survives reload, recovers missing route, keeps admin access and avoids duplicate HTTP routes')


if __name__ == '__main__':
    from pathlib import Path
    import sys
    import types
    import tempfile
    from homeassistant.core import HomeAssistant
    root = Path(__file__).resolve().parents[1]
    for name, path in [('custom_components', root/'custom_components'),
                       ('custom_components.lotto_645', root/'custom_components/lotto_645')]:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules.setdefault(name, module)
    async def run():
        with tempfile.TemporaryDirectory() as folder:
            hass = HomeAssistant(folder)
            await check_panel_lifecycle(hass)
            await hass.async_stop(force=True)
    asyncio.run(run())
