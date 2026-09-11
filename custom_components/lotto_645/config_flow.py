"""Config and options flow for Lotto 6/45 Analysis."""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_AUTO_GENERATE,
    CONF_AI_TASK_ENTITY_ID,
    CONF_ALLOW_OFFICIAL_FALLBACK,
    CONF_ENABLE_AI,
    CONF_SAJU_BIRTH_DATE,
    CONF_SAJU_BIRTH_PLACE,
    CONF_SAJU_BIRTH_TIME,
    CONF_SAJU_CALENDAR,
    CONF_SAJU_GENDER,
    CONF_SAJU_LONGITUDE,
    CONF_SAJU_LUNAR_LEAP_MONTH,
    CONF_SAJU_TIMEZONE,
    CONF_SAJU_TRUE_SOLAR_TIME,
    CONF_SELECTED_METHODS,
    DEFAULT_AI_AUTO_GENERATE,
    DEFAULT_ALLOW_OFFICIAL_FALLBACK,
    DEFAULT_ENABLE_AI,
    DEFAULT_SAJU_CALENDAR,
    DEFAULT_SAJU_TIMEZONE,
    DEFAULT_SAJU_TRUE_SOLAR_TIME,
    DOMAIN,
    NAME,
)
from .methods import (
    DEFAULT_METHOD_IDS,
    METHOD_MYUNGRI_HETU,
    method_selector_options,
    normalize_method_ids,
)
from .myungri import SajuProfileError, extract_saju_profile, validate_saju_profile

_LOGGER = logging.getLogger(__name__)


def _method_selector() -> selector.SelectSelector:
    """Return the multiple recommendation-method selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=method_selector_options(),
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the main options form."""
    selected = list(
        normalize_method_ids(options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS))
    )
    ai_entity = options.get(CONF_AI_TASK_ENTITY_ID)
    ai_marker: vol.Marker = (
        vol.Optional(
            CONF_AI_TASK_ENTITY_ID,
            description={"suggested_value": ai_entity},
        )
        if ai_entity
        else vol.Optional(CONF_AI_TASK_ENTITY_ID)
    )
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_METHODS, default=selected): _method_selector(),
            vol.Optional(
                CONF_ENABLE_AI,
                default=bool(options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI)),
            ): selector.BooleanSelector(),
            ai_marker: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="ai_task")
            ),
            vol.Optional(
                CONF_AI_AUTO_GENERATE,
                default=bool(
                    options.get(CONF_AI_AUTO_GENERATE, DEFAULT_AI_AUTO_GENERATE)
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ALLOW_OFFICIAL_FALLBACK,
                default=bool(
                    options.get(
                        CONF_ALLOW_OFFICIAL_FALLBACK,
                        DEFAULT_ALLOW_OFFICIAL_FALLBACK,
                    )
                ),
            ): selector.BooleanSelector(),
        }
    )


def _optional_suggested_number(key: str, options: dict[str, Any]) -> vol.Marker:
    """Create a number marker without serializing suggested_value=None.

    Home Assistant frontends are stricter about selector metadata than plain
    voluptuous schemas.  Omitting the suggestion entirely when no value exists
    avoids a generic `Unknown error occurred` while entering the Saju step.
    """
    value = options.get(key)
    if value in (None, ""):
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


def _saju_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the required personal Four Pillars input form."""
    calendar = str(options.get(CONF_SAJU_CALENDAR, DEFAULT_SAJU_CALENDAR))
    gender = str(options.get(CONF_SAJU_GENDER, "male"))
    birth_date = str(options.get(CONF_SAJU_BIRTH_DATE, "") or "")
    birth_time = str(options.get(CONF_SAJU_BIRTH_TIME, "") or "")
    birth_place = str(options.get(CONF_SAJU_BIRTH_PLACE, "") or "")
    timezone = str(
        options.get(CONF_SAJU_TIMEZONE, DEFAULT_SAJU_TIMEZONE)
        or DEFAULT_SAJU_TIMEZONE
    )

    date_marker: vol.Marker = (
        vol.Required(CONF_SAJU_BIRTH_DATE, default=birth_date)
        if birth_date
        else vol.Required(CONF_SAJU_BIRTH_DATE)
    )
    time_marker: vol.Marker = (
        vol.Required(CONF_SAJU_BIRTH_TIME, default=birth_time)
        if birth_time
        else vol.Required(CONF_SAJU_BIRTH_TIME)
    )
    place_marker: vol.Marker = (
        vol.Required(CONF_SAJU_BIRTH_PLACE, default=birth_place)
        if birth_place
        else vol.Required(CONF_SAJU_BIRTH_PLACE)
    )
    longitude_marker = _optional_suggested_number(CONF_SAJU_LONGITUDE, options)

    return vol.Schema(
        {
            vol.Required(CONF_SAJU_CALENDAR, default=calendar): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "solar", "label": "양력"},
                        {"value": "lunar", "label": "음력"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            date_marker: selector.DateSelector(),
            time_marker: selector.TimeSelector(),
            vol.Required(CONF_SAJU_GENDER, default=gender): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "male", "label": "남성"},
                        {"value": "female", "label": "여성"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            place_marker: selector.TextSelector(),
            vol.Required(CONF_SAJU_TIMEZONE, default=timezone): selector.TextSelector(),
            vol.Optional(
                CONF_SAJU_LUNAR_LEAP_MONTH,
                default=bool(options.get(CONF_SAJU_LUNAR_LEAP_MONTH, False)),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SAJU_TRUE_SOLAR_TIME,
                default=bool(
                    options.get(
                        CONF_SAJU_TRUE_SOLAR_TIME,
                        DEFAULT_SAJU_TRUE_SOLAR_TIME,
                    )
                ),
            ): selector.BooleanSelector(),
            longitude_marker: selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180,
                    max=180,
                    step=0.0001,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _normalize_submitted_methods(raw_methods: object) -> tuple[str, ...]:
    """Validate a frontend multiple-select payload without assuming list type."""
    if not isinstance(raw_methods, (list, tuple)) or not raw_methods:
        return ()
    submitted = [str(value) for value in raw_methods]
    normalized = normalize_method_ids(submitted)
    if len(normalized) != len(dict.fromkeys(submitted)):
        return ()
    return normalized


class Lotto645ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lotto 6/45 Analysis."""

    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> "Lotto645OptionsFlow":
        return Lotto645OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class Lotto645OptionsFlow(OptionsFlow):
    """Manage recommendation, personal Saju, AI, and cautious source options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._options = dict(config_entry.options)
        self._pending_options: dict[str, Any] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select recommendation methods and optional AI/source behavior."""
        errors: dict[str, str] = {}
        if user_input is not None:
            normalized = _normalize_submitted_methods(
                user_input.get(CONF_SELECTED_METHODS)
            )
            if not normalized:
                errors[CONF_SELECTED_METHODS] = "select_at_least_one"
            else:
                try:
                    pending = dict(self._options)
                    pending.update(user_input)
                    pending[CONF_SELECTED_METHODS] = list(normalized)
                    if not pending.get(CONF_AI_TASK_ENTITY_ID):
                        pending.pop(CONF_AI_TASK_ENTITY_ID, None)
                    self._pending_options = pending
                    if METHOD_MYUNGRI_HETU in normalized:
                        # This is intentionally a second step.  Birth information
                        # is never requested unless the user selected 명리 권장.
                        return await self.async_step_saju()
                    self._pending_options = None
                    return self.async_create_entry(title="", data=pending)
                except (TypeError, ValueError) as err:
                    _LOGGER.exception("로또 옵션 저장 준비 중 오류: %s", err)
                    errors["base"] = "options_error"

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._options),
            errors=errors,
        )

    async def async_step_saju(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require and validate personal birth information before enabling 명리."""
        source = dict(self._options)
        if self._pending_options is not None:
            source.update(self._pending_options)
        errors: dict[str, str] = {}

        if user_input is not None:
            pending = dict(source)
            clean = dict(user_input)
            clean[CONF_SAJU_BIRTH_DATE] = str(
                clean.get(CONF_SAJU_BIRTH_DATE, "") or ""
            )
            clean[CONF_SAJU_BIRTH_TIME] = str(
                clean.get(CONF_SAJU_BIRTH_TIME, "") or ""
            )
            if clean.get(CONF_SAJU_CALENDAR) != "lunar":
                clean[CONF_SAJU_LUNAR_LEAP_MONTH] = False
            if not clean.get(CONF_SAJU_TRUE_SOLAR_TIME):
                clean.pop(CONF_SAJU_LONGITUDE, None)
            pending.update(clean)
            profile = extract_saju_profile(pending)
            try:
                validate_saju_profile(profile)
            except SajuProfileError as err:
                _LOGGER.debug("개인 사주정보 검증 실패: %s", err)
                errors["base"] = "invalid_saju_profile"
            except (TypeError, ValueError) as err:
                _LOGGER.exception("개인 사주정보 처리 중 오류: %s", err)
                errors["base"] = "options_error"
            else:
                self._pending_options = None
                return self.async_create_entry(title="", data=pending)
            source = pending

        return self.async_show_form(
            step_id="saju",
            data_schema=_saju_schema(source),
            errors=errors,
        )
