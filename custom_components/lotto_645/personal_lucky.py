"""Local, versioned keyword personalization. Never expose raw input to AI/logs."""
from __future__ import annotations

from hashlib import sha256
import json
import unicodedata

KEYWORD_KEY = 'lucky_keyword'
THEME_KEY = 'lucky_theme'
THEMES = ('keyword', 'dream', 'wish')


def normalize_keyword(value):
    if not isinstance(value, str) or len(value) > 160:
        raise ValueError('행운 키워드는 80자 이내의 문자열로 입력하세요')
    value = ' '.join(unicodedata.normalize('NFKC', value).split())
    if len(value) > 80 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('행운 키워드의 길이와 제어 문자를 확인하세요')
    return value or '행운'


def generate(keyword='행운', *, theme='keyword', target_round, rng=None, blocked=()):
    """SHA-256 counter stream with unbiased randrange, then partial shuffle.

    A fresh 256-bit nonce per generation means refresh regenerates; cached
    tickets preserve the exact result across restart. No user seed is accepted.
    """
    from secrets import SystemRandom
    from .sampling import generate_ticket
    keyword = normalize_keyword(keyword)
    if theme not in THEMES:
        raise ValueError('지원하지 않는 행운 번호 테마입니다')
    rng = rng if rng is not None else SystemRandom()
    payload = json.dumps(['personal_lucky_v1', keyword, theme, target_round,
                          rng.randrange(1 << 256)], ensure_ascii=False, separators=(',', ':')).encode()

    class Stream:
        counter = 0

        def randrange(self, stop):
            if type(stop) is not int or not 0 < stop <= (1 << 256):
                raise ValueError('Invalid range')
            limit = (1 << 256) - (1 << 256) % stop
            while True:
                raw = int.from_bytes(sha256(payload + self.counter.to_bytes(8, 'big')).digest(), 'big')
                self.counter += 1
                if raw < limit:
                    return raw % stop

    return generate_ticket('uniform_fisher_yates', excluded_combinations=blocked, rng=Stream())
