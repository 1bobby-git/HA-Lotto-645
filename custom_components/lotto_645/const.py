"""Constants for Lotto 6/45 Analysis."""

from datetime import timedelta

DOMAIN = "lotto_645"
NAME = "Lotto 6/45 Analysis"
VERSION = "1.0.0"

PLATFORMS = ["sensor", "button"]

UPDATE_INTERVAL = timedelta(hours=6)
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.history"

SERVICE_REFRESH = "refresh"

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
