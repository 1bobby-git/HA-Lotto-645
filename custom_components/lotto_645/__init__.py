"""Lotto 6/45 Analysis integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_utc_time_change

from .const import DOMAIN, SERVICE_GENERATE_AI, SERVICE_REFRESH
from .research_extension import install_research_extensions

# Install additive research formulas before coordinator, ticket-panel schemas,
# config flows or validation code import the formula catalog.
install_research_extensions()

from .coordinator import Lotto645Coordinator
from .ticket_panel import async_register_ticket_panel, async_remove_ticket_panel, async_ensure_ticket_panel

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]

# GitHub mirror: Sat 20:45/21:10/21:40/22:20/22:50 KST and Sun 09:30.
# Client checks follow 10 minutes later; weekday is datetime.weekday().
_RESULT_CHECKS_UTC = (
    (5, 11, 55), (5, 12, 20), (5, 12, 50),
    (5, 13, 30), (5, 14, 0), (6, 0, 40),
)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after selected methods or AI options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lotto 6/45 Analysis from a config entry."""
    await async_register_ticket_panel(hass, entry)
    coordinator = Lotto645Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    from .research_runtime import async_register_research_commands
    async_register_research_commands(hass)
    from .portfolio_runtime import async_register_portfolio_commands
    async_register_portfolio_commands(hass)
    from .validation_lifecycle import async_setup_validation
    await async_setup_validation(hass, coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _publication_tick(now) -> None:
        async_ensure_ticket_panel(hass)
        await coordinator.async_poll_published_results()

    entry.async_on_unload(async_track_utc_time_change(hass, _publication_tick, second=15))

    for weekday, hour, minute in _RESULT_CHECKS_UTC:
        async def _scheduled_result_check(now, expected_weekday=weekday) -> None:
            if now.weekday() != expected_weekday:
                return
            await entry.runtime_data.async_check_draw_result()

        entry.async_on_unload(
            async_track_utc_time_change(
                hass, _scheduled_result_check, hour=hour, minute=minute, second=0
            )
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def _handle_refresh(call: ServiceCall) -> None:
            del call
            await entry.runtime_data.async_refresh_and_regenerate()

        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_AI):

        async def _handle_generate_ai(call: ServiceCall) -> None:
            entity_id = call.data.get(ATTR_ENTITY_ID)
            await entry.runtime_data.async_generate_ai_recommendation(entity_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_AI,
            _handle_generate_ai,
            schema=vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_id}),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        from .historical_validation_runtime import LAST_KEY
        hass.data.get(LAST_KEY, {}).pop(entry.entry_id, None)
        await entry.runtime_data.async_flush_consensus()
        async_remove_ticket_panel(hass, entry.entry_id)
        if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
        if hass.services.has_service(DOMAIN, SERVICE_GENERATE_AI):
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_AI)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the panel only when the entry is really deleted, not reloaded."""
    async_remove_ticket_panel(hass, entry.entry_id, permanent=True)
