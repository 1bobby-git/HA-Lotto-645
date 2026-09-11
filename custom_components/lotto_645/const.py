"""Constants for Lotto 6/45 Analysis."""

from datetime import timedelta

DOMAIN = "lotto_645"
NAME = "Lotto 6/45 Analysis"
VERSION = "1.2.1"

PLATFORMS = ["sensor", "button"]

UPDATE_INTERVAL = timedelta(hours=6)
STORAGE_VERSION = 2
STORAGE_KEY_PREFIX = f"{DOMAIN}.history"

SERVICE_REFRESH = "refresh"
SERVICE_GENERATE_AI = "generate_ai_recommendation"

CONF_SELECTED_METHODS = "selected_methods"
CONF_ENABLE_AI = "enable_ai_recommendation"
CONF_AI_TASK_ENTITY_ID = "ai_task_entity_id"
CONF_AI_AUTO_GENERATE = "ai_auto_generate"

DEFAULT_ENABLE_AI = False
DEFAULT_AI_AUTO_GENERATE = False
AI_METHOD_ID = "home_assistant_ai"
AI_MAX_ATTEMPTS = 2

MAIN_INFO_URL = "https://dhlottery.co.kr/selectMainInfo.do"
HISTORY_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
SINGLE_DRAW_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
SOURCE_NAME = "동행복권 로또 6/45"
SOURCE_RESULT_URL = "https://www.dhlottery.co.kr/lt645/result"

FIRST_PRIZE_ODDS = "1/8,145,060"
DISCLAIMER = (
    "로또 추첨은 독립적인 무작위 사건이며 당첨을 보장하거나 실제 당첨 확률을 "
    "높이는 공식은 없습니다. 모든 6개 조합의 1등 확률은 동일합니다."
)
PUBLIC_FORMULA_NOTICE = (
    "공개 공식이라는 명칭은 널리 알려진 빈도·간격·균형·델타·이월수 등의 "
    "분석 규칙을 뜻하며 검증된 당첨 공식이라는 의미가 아닙니다."
)
