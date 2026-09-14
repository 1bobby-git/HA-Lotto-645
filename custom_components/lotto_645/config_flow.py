"""Config and options flow for Lotto 6/45 Analysis."""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
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
    CONF_SAJU_LUNAR_STANDARD,
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
    DEFAULT_METHOD_IDS, ACTIVE_METHOD_IDS, UNIFORM_ENGINES, FREQUENCY_PRESETS,
    CONF_UNIFORM_ENGINE, CONF_FREQUENCY_PRESET, consolidate_options,
    METHOD_MYUNGRI_HETU,
    METHOD_SELECTED_MEDIAN,
    consensus_source_ids,
    METHODS_BY_ID,
    method_selector_options,
    normalize_method_ids,
)
from .myungri import (
    SajuProfileError,
    extract_saju_profile,
    has_complete_saju_profile,
    validate_saju_profile,
)
from .saju_calendar import normalize_birth_date, normalize_birth_time
from .purchased_tickets import SLOTS, PurchaseInputError, parse_round

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
    if key == CONF_SAJU_BIRTH_DATE:
        value = normalize_birth_date(value)
    elif key == CONF_SAJU_BIRTH_TIME:
        value = normalize_birth_time(value)
    if value:
        return vol.Required(key, default=value)
    return vol.Required(key)


def _recommendation_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the small, stable recommendation/AI/source options form."""
    options = consolidate_options(options)
    selected = options[CONF_SELECTED_METHODS]
    ai_entity_marker = _optional_text_marker(CONF_AI_TASK_ENTITY_ID, options)
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_METHODS, default=selected): _method_selector(),
            vol.Optional(CONF_UNIFORM_ENGINE, default=options[CONF_UNIFORM_ENGINE]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[{"value": key, "label": METHODS_BY_ID[key].label}
                                                       for key in UNIFORM_ENGINES],
                                              mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_FREQUENCY_PRESET, default=options[CONF_FREQUENCY_PRESET]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[{"value": key, "label": METHODS_BY_ID[key].label}
                                                       for key in FREQUENCY_PRESETS],
                                              mode=selector.SelectSelectorMode.DROPDOWN)),
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
            vol.Required(CONF_SAJU_LUNAR_STANDARD, default=str(options.get(
                CONF_SAJU_LUNAR_STANDARD, "chinese" if options.get(CONF_SAJU_CALENDAR) == "lunar" else "korean"
            ))): selector.SelectSelector(selector.SelectSelectorConfig(
                options=[{"value": "korean", "label": "한국 음력"}, {"value": "chinese", "label": "중국 음력 (기존 호환)"}],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )),
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
    if any(value not in ACTIVE_METHOD_IDS for value in submitted):
        return ()
    normalized = normalize_method_ids(submitted)
    if len(normalized) != len(dict.fromkeys(submitted)):
        return ()
    return normalized


class Lotto645ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lotto 6/45 Analysis."""

    VERSION = 2
    MINOR_VERSION = 2

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
        self._entry = config_entry
        self._purchase_round: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a schema-free menu so opening Configure cannot fail on selectors."""
        del user_input
        return self.async_show_menu(
            step_id="init",
            menu_options=["recommendations", "saju", "purchases"],
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
                elif (
                    METHOD_SELECTED_MEDIAN in normalized
                    and len(consensus_source_ids(normalized)) < 2
                ):
                    errors["base"] = "consensus_sources_required"
                else:
                    pending = consolidate_options(self._options)
                    pending.update(user_input)
                    if any(pending.get(key) not in allowed for key, allowed in (
                        (CONF_UNIFORM_ENGINE, UNIFORM_ENGINES), (CONF_FREQUENCY_PRESET, FREQUENCY_PRESETS)
                    )):
                        raise ValueError("지원하지 않는 공식 옵션입니다")
                    pending[CONF_SELECTED_METHODS] = list(normalized)
                    if not pending.get(CONF_AI_TASK_ENTITY_ID):
                        pending.pop(CONF_AI_TASK_ENTITY_ID, None)

                    if METHOD_MYUNGRI_HETU in normalized:
                        profile = extract_saju_profile(pending)
                        if not await self.hass.async_add_executor_job(has_complete_saju_profile, profile):
                            errors["base"] = "saju_profile_required"
                        else:
                            try:
                                await self.hass.async_add_executor_job(validate_saju_profile, profile)
                            except SajuProfileError as err:
                                _LOGGER.debug("개인 사주정보 검증 실패: %s", err)
                                errors["base"] = "invalid_saju_profile"

                    if not errors:
                        return self.async_create_entry(title="", data=pending)
            except (TypeError, ValueError) as err:
                _LOGGER.exception("추첨 공식 옵션 처리 중 오류: %s", err)
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
                pending[CONF_SAJU_BIRTH_DATE] = normalize_birth_date(
                    pending.get(CONF_SAJU_BIRTH_DATE, "")
                )
                pending[CONF_SAJU_BIRTH_TIME] = normalize_birth_time(
                    pending.get(CONF_SAJU_BIRTH_TIME, "")
                )
                await self.hass.async_add_executor_job(validate_saju_profile, extract_saju_profile(pending))
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


    async def async_step_purchases(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the draw printed on the user's ticket before entering A–E."""
        coordinator = getattr(self._entry, "runtime_data", None)
        if coordinator is None or coordinator.data is None:
            return self.async_abort(reason="purchase_integration_not_ready")
        if coordinator.purchase_storage_error:
            return self.async_abort(reason="purchase_storage_unavailable")
        errors = {}
        default_round = str(coordinator.data.analysis.target_round)
        if user_input is not None:
            default_round = str(user_input.get("purchase_round", ""))
            try:
                self._purchase_round = parse_round(default_round)
            except PurchaseInputError as err:
                errors[err.field] = err.code
            else:
                return await self.async_step_purchase_games()
        return self.async_show_form(
            step_id="purchases",
            data_schema=vol.Schema({
                vol.Required("purchase_round", default=default_round): selector.TextSelector(),
            }),
            errors=errors,
            description_placeholders={
                "saved_rounds": ", ".join(map(str, sorted(map(int, coordinator.purchase_book.records)))) or "-"
            },
        )

    async def async_step_purchase_games(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter up to five six-number games; blank slots are optional."""
        coordinator = getattr(self._entry, "runtime_data", None)
        if coordinator is None or coordinator.data is None:
            return self.async_abort(reason="purchase_integration_not_ready")
        if self._purchase_round is None:
            return await self.async_step_purchases()
        errors = {}
        form_values = coordinator.purchase_book.form_values(self._purchase_round)
        if user_input is not None:
            form_values = dict(user_input)
            try:
                await coordinator.async_save_purchase_record(
                    self._purchase_round, user_input, clear=bool(user_input.get("clear_round", False))
                )
            except PurchaseInputError as err:
                errors[err.field] = err.code
            except (HomeAssistantError, OSError):
                errors["base"] = "purchase_storage_unavailable"
            else:
                # Tickets live in their own local Store, not recommendation options.
                return self.async_create_entry(title="", data=dict(self._entry.options))
        schema = {
            vol.Optional(f"game_{slot.lower()}", default=str(form_values.get(f"game_{slot.lower()}", "") or "")): selector.TextSelector()
            for slot in SLOTS
        }
        schema[vol.Optional("clear_round", default=False)] = selector.BooleanSelector()
        return self.async_show_form(
            step_id="purchase_games", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={"round": str(self._purchase_round)},
        )
