"""Translation-file regression tests mirroring Home Assistant hassfest rules."""
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/lotto_645'
TRANSLATION_FILES = [COMPONENT / 'strings.json', *sorted((COMPONENT / 'translations').glob('*.json'))]

# Same pattern as script/hassfest/translations.py RE_URL: hassfest rejects any
# translation string containing a URL and asks for description placeholders.
HASSFEST_URL = re.compile(
    r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5):\/\/|www\.)"
    r"[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?)",
    re.IGNORECASE,
)


def _strings(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, (*path, key))
    elif isinstance(node, str):
        yield '.'.join(path), node


@pytest.mark.parametrize('path', TRANSLATION_FILES, ids=lambda p: p.relative_to(COMPONENT).as_posix())
def test_translation_strings_contain_no_urls(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    offenders = [key for key, value in _strings(data) if HASSFEST_URL.search(value)]
    assert offenders == []
