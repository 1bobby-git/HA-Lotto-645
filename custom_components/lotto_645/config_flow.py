"""Config and options flow for Lotto 6/45 Analysis."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_AUTO_GENERATE,
    CONF_AI_TASK_ENTITY_ID,
    CONF_ENABLE_AI,
    CONF_SELECTED_METHODS,
    DEFAULT_AI_AUTO_GENERATE,
    DEFAULT_ENABLE_AI,
    DOMAIN,
    NAME,
)
from .methods import (
    DEFAULT_METHOD_IDS,
    method_selector_options,
    normalize_method_ids,
)


def _method_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=method_selector_options(),
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    selected = list(
        normalize_method_ids(
            options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS)
        )
    )
    ai_entity = options.get(CONF_AI_TASK_ENTITY_ID)
    ai_entity_marker: vol.Marker
    if ai_entity:
        ai_entity_marker = vol.Optional(
            CONF_AI_TASK_ENTITY_ID,
            description={"suggested_value": ai_entity},
        )
    else:
        ai_entity_marker = vol.Optional(CONF_AI_TASK_ENTITY_ID)

    return vol.Schema(
        {
            vol.Required(
                CONF_SELECTED_METHODS,
                default=selected,
            ): _method_selector(),
            vol.Optional(
                CONF_ENABLE_AI,
                default=options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI),
            ): selector.BooleanSelector(),
            ai_entity_marker: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="ai_task")
            ),
            vol.Optional(
                CONF_AI_AUTO_GENERATE,
                default=options.get(
                    CONF_AI_AUTO_GENERATE, DEFAULT_AI_AUTO_GENERATE
                ),
            ): selector.BooleanSelector(),
        }
    )


class Lotto645ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lotto 6/45 Analysis."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> "Lotto645OptionsFlow":
        """Return the options flow."""
        return Lotto645OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )


class Lotto645OptionsFlow(OptionsFlow):
    """Manage selectable formulas and Home Assistant AI Task options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save integration options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw_methods = user_input.get(CONF_SELECTED_METHODS)
            if not isinstance(raw_methods, list) or not raw_methods:
                errors[CONF_SELECTED_METHODS] = "select_at_least_one"
            else:
                normalized = normalize_method_ids(raw_methods)
                if not normalized:
                    errors[CONF_SELECTED_METHODS] = "select_at_least_one"
                else:
                    user_input[CONF_SELECTED_METHODS] = list(normalized)
                    if not user_input.get(CONF_AI_TASK_ENTITY_ID):
                        user_input.pop(CONF_AI_TASK_ENTITY_ID, None)
                    return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._options),
            errors=errors,
        )
