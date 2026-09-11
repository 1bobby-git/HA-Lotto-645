"""Lotto 6/45 Analysis integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_GENERATE_AI, SERVICE_REFRESH
from .coordinator import Lotto645Coordinator

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after selected methods or AI options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lotto 6/45 Analysis from a config entry."""
    coordinator = Lotto645Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def _handle_refresh(call: ServiceCall) -> None:
            del call
            await entry.runtime_data.async_request_refresh()

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
        if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
        if hass.services.has_service(DOMAIN, SERVICE_GENERATE_AI):
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_AI)
    return unloaded
