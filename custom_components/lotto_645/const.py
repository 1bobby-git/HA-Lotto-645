"""Constants for Lotto 6/45 Analysis."""

from datetime import timedelta

DOMAIN = "lotto_645"
NAME = "Lotto 6/45 Analysis"
VERSION = "1.15.1"

PLATFORMS = ["sensor", "button", "binary_sensor"]
UPDATE_INTERVAL = timedelta(hours=6)
STORAGE_VERSION = 3
STORAGE_KEY_PREFIX = f"{DOMAIN}.history"

SERVICE_REFRESH = "refresh"
SERVICE_GENERATE_AI = "generate_ai_recommendation"

CONF_SELECTED_METHODS = "selected_methods"
CONF_ENABLE_AI = "enable_ai_recommendation"
CONF_AI_TASK_ENTITY_ID = "ai_task_entity_id"
CONF_AI_AUTO_GENERATE = "ai_auto_generate"
CONF_ALLOW_OFFICIAL_FALLBACK = "allow_official_direct_fallback"

# Personal Four Pillars / Saju profile. These values stay inside the user's
# Home Assistant config entry and are never sent to the lottery mirror.
CONF_SAJU_CALENDAR = "saju_calendar"
CONF_SAJU_LUNAR_STANDARD = "saju_lunar_standard"
CONF_SAJU_BIRTH_DATE = "saju_birth_date"
CONF_SAJU_BIRTH_TIME = "saju_birth_time"
CONF_SAJU_LUNAR_LEAP_MONTH = "saju_lunar_leap_month"
CONF_SAJU_GENDER = "saju_gender"

# ... remaining constants are unchanged below in the repository version.
