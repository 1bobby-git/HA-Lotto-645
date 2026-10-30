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


def _paths(node, path=()):
    """Every key path, including empty sections, so missing and stale keys both show."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield '.'.join((*path, key))
            yield from _paths(value, (*path, key))


@pytest.mark.parametrize('path', TRANSLATION_FILES[1:], ids=lambda p: p.name)
def test_every_translation_has_exactly_the_strings_json_keys(path):
    expected = set(_paths(json.loads((COMPONENT / 'strings.json').read_text(encoding='utf-8'))))
    actual = set(_paths(json.loads(path.read_text(encoding='utf-8'))))
    assert sorted(expected - actual) == [], 'missing keys'
    assert sorted(actual - expected) == [], 'stale keys'


def test_english_translation_is_the_strings_json_source():
    # Custom integrations load translations/en.json at runtime; strings.json is
    # the English source that hassfest validates. They must not drift apart.
    source = json.loads((COMPONENT / 'strings.json').read_text(encoding='utf-8'))
    english = json.loads((COMPONENT / 'translations/en.json').read_text(encoding='utf-8'))
    assert english == source
