"""Normalize only formula options; never include Saju/AI credentials in caches."""
from dataclasses import asdict
from hashlib import sha256
import json

from .constraints import Rules, RULES_KEY
from .personal_lucky import KEYWORD_KEY, THEME_KEY, THEMES, normalize_keyword

CONSTRAINT_ID = 'constraint_uniform'
LUCKY_ID = 'personal_lucky'
CUSTOM_IDS = (CONSTRAINT_ID, LUCKY_ID)


def settings(options=None):
    options = options or {}
    theme = options.get(THEME_KEY, 'keyword')
    if theme not in THEMES:
        raise ValueError('지원하지 않는 행운 번호 테마입니다')
    return {RULES_KEY: asdict(Rules.parse(options.get(RULES_KEY))),
            KEYWORD_KEY: normalize_keyword(options.get(KEYWORD_KEY, '행운')), THEME_KEY: theme}


def fingerprint(options, method_ids):
    if not set(method_ids).intersection(CUSTOM_IDS):
        return None
    normalized = settings(options)
    selected = {}
    if CONSTRAINT_ID in method_ids:
        selected[RULES_KEY] = normalized[RULES_KEY]
    if LUCKY_ID in method_ids:
        selected.update({key: normalized[key] for key in (KEYWORD_KEY, THEME_KEY)})
    # Stored locally only; never added to sensor attributes or AI prompts.
    return sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if selected else None
