from pathlib import Path
import json
root=Path('.'); c=root/'custom_components/lotto_645'
p=c/'ticket_panel.py';s=p.read_text()
s=s.replace('from pathlib import Path','import asyncio\nfrom pathlib import Path')
s=s.replace('from homeassistant.core import HomeAssistant','from homeassistant.core import HomeAssistant\nfrom homeassistant.config_entries import ConfigEntryState')
s=s.replace("    if entry is None or entry.domain != DOMAIN or not getattr(entry, 'runtime_data', None):", "    if (entry is None or entry.domain != DOMAIN or not getattr(entry, 'runtime_data', None)\n            or getattr(entry, 'state', ConfigEntryState.LOADED) != ConfigEntryState.LOADED):")
a=s.index('async def async_register_ticket_panel(')
s=s[:a]+'''def _shared(hass: HomeAssistant) -> dict:
    shared = hass.data.setdefault(KEY, {'entries': {}, 'registered': False})
    shared.setdefault('lock', asyncio.Lock())
    return shared


def _install_panel(hass: HomeAssistant, shared: dict) -> None:
    """Update our panel atomically. Never remove a working route before rebuild."""
    config = {
        'entries': dict(shared['entries']), 'version': VERSION,
        'logo_url': f'/lotto_645_brand/logo.png?v={VERSION}',
        '_panel_custom': {'name': 'lotto-ticket-panel', 'embed_iframe': False,
                          'trust_external': False, 'handle_safe_area': False,
                          'module_url': f'/lotto_645_static/lotto-panel.js?v={VERSION}'},
    }
    current = hass.data.get(frontend.DATA_PANELS, {}).get(PATH)
    if current is not None and (current.config or {}).get('_panel_custom', {}).get('name') != 'lotto-ticket-panel':
        raise HomeAssistantError('lotto-645 경로를 다른 대시보드가 사용하고 있습니다')
    frontend.async_register_built_in_panel(
        hass, 'custom', frontend_url_path=PATH, sidebar_title='로또 복권',
        sidebar_icon='mdi:ticket-confirmation', require_admin=True,
        config=config, update=current is not None,
    )


async def async_register_ticket_panel(hass: HomeAssistant, entry=None) -> None:
    """Idempotent singleton routes/commands; safe during multi-entry reloads."""
    shared = _shared(hass)
    async with shared['lock']:
        if entry is not None:
            shared['entries'][entry.entry_id] = entry.title
        # Entries survive an options reload; only actual config-entry removal
        # removes their route membership. Backend access still checks LOADED.
        if not shared['registered']:
            await hass.http.async_register_static_paths([
                StaticPathConfig('/lotto_645_static', str(WWW), False),
            ])
            for handler in (purchases_get, qr_preview, purchases_save, result_check):
                websocket_api.async_register_command(hass, handler)
            shared['registered'] = True
        if not shared.get('brand_registered'):
            await hass.http.async_register_static_paths([
                StaticPathConfig('/lotto_645_brand', str(Path(__file__).parent / 'brand'), False),
            ])
            shared['brand_registered'] = True
        if shared['entries']:
            _install_panel(hass, shared)


async def async_restore_ticket_panel(hass: HomeAssistant) -> None:
    """Rebuild a missing sidebar route without refreshing numbers or stores."""
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
               if getattr(entry, 'disabled_by', None) is None]
    shared = _shared(hass)
    shared['entries'] = {entry.entry_id: entry.title for entry in entries}
    if entries:
        await async_register_ticket_panel(hass)


def async_remove_ticket_panel(hass: HomeAssistant, entry_id: str) -> None:
    """Called ONLY when the user deletes a config entry, not on reload."""
    shared = hass.data.get(KEY)
    if shared:
        shared['entries'].pop(entry_id, None)
        if shared['entries']:
            _install_panel(hass, shared)
        else:
            frontend.async_remove_panel(hass, PATH)
'''
s=s.replace('from homeassistant.components import frontend, panel_custom, websocket_api','from homeassistant.components import frontend, websocket_api')
p.write_text(s)
p=c/'__init__.py';s=p.read_text();s=s.replace('from homeassistant.const import ATTR_ENTITY_ID, Platform','from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STARTED, Platform')
s=s.replace('from .ticket_panel import async_register_ticket_panel, async_remove_ticket_panel','from .ticket_panel import async_register_ticket_panel, async_remove_ticket_panel, async_restore_ticket_panel')
pos=s.index('async def _async_reload_entry(')
s=s[:pos]+'''async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the management page independently of slow analysis/network setup."""
    del config
    await async_restore_ticket_panel(hass)

    async def _restore(_event=None) -> None:
        await async_restore_ticket_panel(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _restore)
    if not hass.services.has_service(DOMAIN, 'restore_panel'):
        hass.services.async_register(DOMAIN, 'restore_panel', _restore, schema=vol.Schema({}))
    return True


''' +s[pos:]
s=s.replace('    coordinator = Lotto645Coordinator(hass, entry)','    await async_register_ticket_panel(hass, entry)\n    coordinator = Lotto645Coordinator(hass, entry)',1)
s=s.replace('    await async_register_ticket_panel(hass, entry)\n\n    async def _publication_tick', '    async def _publication_tick',1)
s=s.replace('        async_remove_ticket_panel(hass, entry.entry_id)','        # Keep the management route visible while an options reload initializes.\n        # The backend rejects stale/unloaded runtime_data.')
s += '''\n\nasync def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Deleting a config entry removes membership; never delete ticket/review stores."""
    async_remove_ticket_panel(hass, entry.entry_id)
'''
p.write_text(s)
p=c/'entity.py';s=p.read_text().replace('model="추첨 결과 · 구매번호 · 당첨 상세", sw_version=VERSION,','model="추첨 결과 · 구매번호 · 당첨 상세", sw_version=VERSION,\n                configuration_url="/lotto-645",').replace('            sw_version=VERSION,','            sw_version=VERSION,\n            configuration_url="/lotto-645",');p.write_text(s)
p=c/'button.py';s=p.read_text().replace('from homeassistant.helpers.entity_platform import AddEntitiesCallback','from homeassistant.helpers.entity_platform import AddEntitiesCallback\nfrom homeassistant.helpers.entity import EntityCategory');s=s.replace('[LottoRefreshButton(coordinator), LottoResultCheckButton(coordinator)]','[LottoRefreshButton(coordinator), LottoResultCheckButton(coordinator), LottoRestorePanelButton(coordinator)]');s+='''\n\nclass LottoRestorePanelButton(Lotto645Entity, ButtonEntity):
    """Restore sidebar registration without changing any recommendation or ticket."""
    _attr_name = "로또 페이지 복구"
    _attr_icon = "mdi:view-dashboard-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_restore_panel"

    @property
    def available(self) -> bool:
        return True

    async def async_press(self):
        from .ticket_panel import async_restore_ticket_panel
        await async_restore_ticket_panel(self.hass)
''';p.write_text(s)
p=c/'services.yaml';s=p.read_text();s+='''\nrestore_panel:
  name: 로또 페이지 복구
  description: 로또 복권 사이드바 페이지를 다시 등록합니다. 추천번호·구매번호·리뷰를 변경하지 않습니다.
''';p.write_text(s)
for name in ('strings.json','translations/ko.json','translations/en.json'):
 p=c/name;v=json.loads(p.read_text());ko='ko.json' in name
 v.setdefault('services',{})['restore_panel']={'name':'로또 페이지 복구' if ko else 'Restore Lotto page','description':'추천·구매·리뷰를 변경하지 않고 로또 복권 페이지를 다시 등록합니다.' if ko else 'Restore the Lotto sidebar page without changing recommendations, tickets or reviews.'}
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
