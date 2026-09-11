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
from .myungri import (
    SajuProfileError,
    extract_saju_profile,
    has_complete_saju_profile,
    validate_saju_profile,
)

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


def _optional_text_marker(key: str, options: dict[str, Any]) -> vol.Marker:
    """Return a plain optional text marker with a string default when present."""
    value = options.get(key)
    if value in (None, ""):
        return vol.Optional(key)
    return vol.Optional(key, default=str(value))


def _required_text_marker(key: str, options: dict[str, Any]) -> vol.Marker:
    """Return a required text marker without invalid blank defaults."""
    value = str(options.get(key, "") or "").strip()
    if value:
        return vol.Required(key, default=value)
    return vol.Required(key)


def _recommendation_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the small, stable recommendation/AI/source options form."""
    selected = list(
        normalize_method_ids(options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS))
    )
    ai_entity_marker = _optional_text_marker(CONF_AI_TASK_ENTITY_ID, options)
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_METHODS, default=selected): _method_selector(),
            vol.Optional(
                CONF_ENABLE_AI,
                default=bool(options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI)),
            ): selector.BooleanSelector(),
            ai_entity_marker: selector.EntitySelector(
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


def _saju_schema(options: dict[str, Any]) -> vol.Schema:
    """Build a compatibility-first personal Saju form.

    Birth date/time/longitude deliberately use TextSelector instead of the more
    specialized date/time/number selectors.  The integration validates and
    parses the values locally after submission.  This keeps the Options Flow
    serializable across Home Assistant frontend versions and avoids a 400 while
    the flow is being created.
    """
    calendar = str(options.get(CONF_SAJU_CALENDAR, DEFAULT_SAJU_CALENDAR))
    gender = str(options.get(CONF_SAJU_GENDER, "male") or "male")
    timezone = str(
        options.get(CONF_SAJU_TIMEZONE, DEFAULT_SAJU_TIMEZONE)
        or DEFAULT_SAJU_TIMEZONE
    )
    longitude_marker = _optional_text_marker(CONF_SAJU_LONGITUDE, options)

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
            _required_text_marker(CONF_SAJU_BIRTH_DATE, options): selector.TextSelector(),
            _required_text_marker(CONF_SAJU_BIRTH_TIME, options): selector.TextSelector(),
            vol.Required(CONF_SAJU_GENDER, default=gender): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "male", "label": "남성"},
                        {"value": "female", "label": "여성"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            _required_text_marker(CONF_SAJU_BIRTH_PLACE, options): selector.TextSelector(),
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
            longitude_marker: selector.TextSelector(),
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a schema-free menu so opening Configure cannot fail on selectors."""
        del user_input
        return self.async_show_menu(
            step_id="init",
            menu_options=["recommendations", "saju"],
        )

    async def async_step_recommendations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit recommendation methods, AI and cautious source settings."""
        errors: dict[str, str] = {}
        form_values = dict(self._options)
        if user_input is not None:
            form_values.update(user_input)
            try:
                normalized = _normalize_submitted_methods(
                    user_input.get(CONF_SELECTED_METHODS)
                )
                if not normalized:
                    errors[CONF_SELECTED_METHODS] = "select_at_least_one"
                else:
                    pending = dict(self._options)
                    pending.update(user_input)
                    pending[CONF_SELECTED_METHODS] = list(normalized)
                    if not pending.get(CONF_AI_TASK_ENTITY_ID):
                        pending.pop(CONF_AI_TASK_ENTITY_ID, None)

                    if METHOD_MYUNGRI_HETU in normalized:
                        profile = extract_saju_profile(pending)
                        if not has_complete_saju_profile(profile):
                            errors["base"] = "saju_profile_required"
                        else:
                            try:
                                validate_saju_profile(profile)
                            except SajuProfileError as err:
                                _LOGGER.debug("개인 사주정보 검증 실패: %s", err)
                                errors["base"] = "invalid_saju_profile"

                    if not errors:
                        return self.async_create_entry(title="", data=pending)
            except (TypeError, ValueError) as err:
                _LOGGER.exception("추천 방식 옵션 처리 중 오류: %s", err)
                errors["base"] = "options_error"

        return self.async_show_form(
            step_id="recommendations",
            data_schema=_recommendation_schema(form_values),
            errors=errors,
        )

    async def async_step_saju(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit and validate the personal Four Pillars profile independently."""
        errors: dict[str, str] = {}
        form_values = dict(self._options)
        if user_input is not None:
            form_values.update(user_input)
            pending = dict(self._options)
            pending.update(user_input)
            pending[CONF_SAJU_BIRTH_DATE] = str(
                pending.get(CONF_SAJU_BIRTH_DATE, "") or ""
            ).strip()
            pending[CONF_SAJU_BIRTH_TIME] = str(
                pending.get(CONF_SAJU_BIRTH_TIME, "") or ""
            ).strip()
            pending[CONF_SAJU_BIRTH_PLACE] = str(
                pending.get(CONF_SAJU_BIRTH_PLACE, "") or ""
            ).strip()
            pending[CONF_SAJU_TIMEZONE] = str(
                pending.get(CONF_SAJU_TIMEZONE, DEFAULT_SAJU_TIMEZONE)
                or DEFAULT_SAJU_TIMEZONE
            ).strip()
            if pending.get(CONF_SAJU_CALENDAR) != "lunar":
                pending[CONF_SAJU_LUNAR_LEAP_MONTH] = False
            if not pending.get(CONF_SAJU_TRUE_SOLAR_TIME):
                pending.pop(CONF_SAJU_LONGITUDE, None)
            elif pending.get(CONF_SAJU_LONGITUDE) not in (None, ""):
                pending[CONF_SAJU_LONGITUDE] = str(
                    pending[CONF_SAJU_LONGITUDE]
                ).strip()

            try:
                validate_saju_profile(extract_saju_profile(pending))
            except SajuProfileError as err:
                _LOGGER.debug("개인 사주정보 검증 실패: %s", err)
                errors["base"] = "invalid_saju_profile"
            except (TypeError, ValueError) as err:
                _LOGGER.exception("개인 사주정보 처리 중 오류: %s", err)
                errors["base"] = "options_error"
            else:
                return self.async_create_entry(title="", data=pending)
            form_values = pending

        return self.async_show_form(
            step_id="saju",
            data_schema=_saju_schema(form_values),
            errors=errors,
        )
