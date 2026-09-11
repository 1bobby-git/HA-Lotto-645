"""Constants for Lotto 6/45 Analysis."""

from datetime import timedelta

DOMAIN = "lotto_645"
NAME = "Lotto 6/45 Analysis"
VERSION = "1.5.2"

PLATFORMS = ["sensor", "button"]
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
CONF_SAJU_BIRTH_DATE = "saju_birth_date"
CONF_SAJU_BIRTH_TIME = "saju_birth_time"
CONF_SAJU_LUNAR_LEAP_MONTH = "saju_lunar_leap_month"
CONF_SAJU_GENDER = "saju_gender"
CONF_SAJU_BIRTH_PLACE = "saju_birth_place"
CONF_SAJU_TIMEZONE = "saju_timezone"
CONF_SAJU_TRUE_SOLAR_TIME = "saju_true_solar_time"
CONF_SAJU_LONGITUDE = "saju_longitude"

SAJU_PROFILE_KEYS = (
    CONF_SAJU_CALENDAR,
    CONF_SAJU_BIRTH_DATE,
    CONF_SAJU_BIRTH_TIME,
    CONF_SAJU_GENDER,
    CONF_SAJU_BIRTH_PLACE,
    CONF_SAJU_TIMEZONE,
    CONF_SAJU_LUNAR_LEAP_MONTH,
    CONF_SAJU_TRUE_SOLAR_TIME,
    CONF_SAJU_LONGITUDE,
)

DEFAULT_ENABLE_AI = False
DEFAULT_AI_AUTO_GENERATE = False
DEFAULT_ALLOW_OFFICIAL_FALLBACK = False
DEFAULT_SAJU_TIMEZONE = "Asia/Seoul"
DEFAULT_SAJU_CALENDAR = "solar"
DEFAULT_SAJU_TRUE_SOLAR_TIME = False
AI_METHOD_ID = "home_assistant_ai"
AI_MAX_ATTEMPTS = 2

MIRROR_URL = (
    "https://raw.githubusercontent.com/1bobby-git/HA-Lotto-645/"
    "main/data/lotto645-history.json"
)
MAIN_INFO_URL = "https://www.dhlottery.co.kr/selectMainInfo.do"
HISTORY_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
SINGLE_DRAW_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
OFFICIAL_RESULT_URL = "https://www.dhlottery.co.kr/lt645/result"
SOURCE_RESULT_URL = OFFICIAL_RESULT_URL
SOURCE_NAME = "HA-Lotto-645 공유 이력 미러 (동행복권 검증)"

OFFICIAL_MIN_INTERVAL_SECONDS = 3.0
OFFICIAL_MAX_REQUESTS_PER_UPDATE = 4
OFFICIAL_CIRCUIT_BREAKER_SECONDS = 12 * 60 * 60
OFFICIAL_DIRECT_MAX_MISSING_ROUNDS = 2

FIRST_PRIZE_ODDS = "1/8,145,060"
DISCLAIMER = (
    "로또 추첨은 독립적인 무작위 사건이며 당첨을 보장하거나 실제 당첨 확률을 "
    "높이는 공식은 없습니다. 모든 6개 조합의 1등 확률은 동일합니다."
)
PUBLIC_FORMULA_NOTICE = (
    "공개 공식이라는 명칭은 널리 알려진 빈도·간격·균형·델타·이월수 등의 "
    "분석 규칙을 뜻하며 검증된 당첨 공식이라는 의미가 아닙니다."
)
SAJU_NOTICE = (
    "명리 추천은 사용자가 직접 입력한 출생정보로 사주 원국·대운·추첨일 간의 전통 명리 관계를 "
    "재현하는 문화적 휴리스틱입니다. 로또 당첨 확률 상승이 과학적으로 검증된 방식은 아닙니다."
)
SAJU_PRIVACY_NOTICE = (
    "사주 입력값은 Home Assistant 구성 항목에 로컬 저장되며 로또 이력 미러로 전송되지 않습니다. "
    "Home Assistant AI 추천에도 원본 생년월일·출생시각·출생지를 전달하지 않습니다."
)
COLLECTION_POLICY = (
    "기본 수집은 GitHub 공유 미러와 릴리스에 포함된 이력 스냅샷을 사용합니다. "
    "각 Home Assistant 설치가 동행복권 전체 회차를 반복 수집하지 않습니다. "
    "동행복권 직접 증분 확인은 사용자가 옵션으로 허용한 경우에만 제한적으로 수행합니다."
)
