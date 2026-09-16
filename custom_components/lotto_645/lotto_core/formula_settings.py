"""Normalize public generation constraints only."""
from dataclasses import asdict
from hashlib import sha256
import json
from .constraints import Rules, RULES_KEY
CONSTRAINT_ID = "constraint_uniform"
CUSTOM_IDS = (CONSTRAINT_ID,)

def settings(options=None):
    return {RULES_KEY: asdict(Rules.parse((options or {}).get(RULES_KEY)))}

def fingerprint(options, method_ids):
    if CONSTRAINT_ID not in method_ids:
        return None
    return sha256(json.dumps(settings(options), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
