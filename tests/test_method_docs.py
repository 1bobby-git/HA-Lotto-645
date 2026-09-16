"""Keep the Korean formula guides aligned with the actual method catalog.

This suite reads Python ASTs without importing Home Assistant or calling a
network. Documentation links and published worked examples are checked too.
"""
from __future__ import annotations

import ast
from collections import Counter
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/lotto_645'
GUIDES = ROOT / 'docs/methods'
ANALYSIS = ast.parse((COMPONENT / 'analysis.py').read_text(encoding='utf-8'))


def catalog() -> list[dict]:
    tree = ast.parse((COMPONENT / 'methods.py').read_text(encoding='utf-8'))
    constants = {
        node.target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    definition = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef) and node.name == 'MethodDefinition')
    defaults = {
        node.target.id: ast.literal_eval(node.value)
        for node in definition.body
        if isinstance(node, ast.AnnAssign) and node.value is not None
    }
    methods = next(node.value for node in tree.body
                   if isinstance(node, ast.AnnAssign)
                   and isinstance(node.target, ast.Name) and node.target.id == 'METHODS')
    individual_function = next(node for node in ANALYSIS.body
                               if isinstance(node, ast.FunctionDef) and node.name == '_component_weights')
    component_dict = next(node for node in ast.walk(individual_function)
                          if isinstance(node, ast.Dict)
                          and any(isinstance(key, ast.Constant) and key.value == 'individual'
                                  for key in node.keys))
    individual = next(ast.literal_eval(value)
                      for key, value in zip(component_dict.keys, component_dict.values)
                      if isinstance(key, ast.Constant) and key.value == 'individual')
    result = []
    for call in methods.elts:
        params = {**defaults, **{kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}}
        method_id = constants[call.args[0].id]
        features = ast.literal_eval(call.args[4])
        if method_id == 'selected_median_consensus':
            assert features == {}, 'Median is dynamically calculated, not a static feature blend'
            assert params['formula_version'] == 2
            features = {}
        weights = {} if params.get('sampling') or method_id in ('selected_median_consensus', 'selected_vote_consensus') else {'individual': individual}
        weights.update({key.removesuffix('_weight'): value for key, value in params.items()
                        if key.endswith('_weight') and value})
        assert not (features.keys() & weights.keys())
        result.append({'id': method_id, 'label': ast.literal_eval(call.args[1]),
                       'pool': params['pool_size'], 'weights': {**features, **weights}})
    return result


CATALOG = catalog()
DOCUMENTS = [ROOT / 'README.md', ROOT / 'docs/FORMULAS.md',
             *[GUIDES / f"{method['id']}.md" for method in CATALOG]]


def test_readme_has_no_changelog_or_version_history():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert not re.search(r'^#{1,6}\s+v?\d+\.\d+\.\d+', text, re.MULTILINE)
    assert '## 추첨 공식 24종' in text
    assert 'changelog' not in text.lower()
    assert not list(ROOT.glob('CHANGELOG*.md'))
    assert not (ROOT / 'docs/RELEASE_V110_CHECKLIST.md').exists()


def test_readme_and_formula_index_link_all_methods_in_catalog_order():
    expected = [(str(index), method['label'], method['id'])
                for index, method in enumerate(CATALOG, 1)]
    assert len(expected) == 22
    for path, prefix in ((ROOT / 'README.md', 'docs/methods/'),
                         (ROOT / 'docs/FORMULAS.md', 'methods/')):
        text = path.read_text(encoding='utf-8')
        matches = re.findall(r'^([0-9]+)\. \[([^\]]+)\]\('
                             + re.escape(prefix) + r'([a-z_]+)\.md\)$', text, re.MULTILINE)
        assert matches == expected, path
    assert {path.stem for path in GUIDES.glob('*.md')} == {m['id'] for m in CATALOG} | {'cycle_rhythm','phase_residual_graph','transition_gap_phase','multiscale_resonance','triplet_cooccurrence'}


@pytest.mark.parametrize('method', CATALOG, ids=[m['id'] for m in CATALOG])
def test_method_metadata_and_weight_tables_match_source(method):
    path = GUIDES / f"{method['id']}.md"
    text = path.read_text(encoding='utf-8')
    assert text.startswith(f"# {method['label']}\n")
    assert f"`method_id: {method['id']}`" in text
    assert f"후보 풀: **{method['pool']}개**" in text
    rows = re.findall(r'^\| `([^`]+)` \| [^|\n]+ \| ([0-9.]+) \|$', text, re.MULTILINE)
    assert len(rows) == len(dict(rows)), 'Duplicate weight keys'
    actual = {key: float(value) for key, value in rows}
    assert actual.keys() == method['weights'].keys()
    for key, value in method['weights'].items():
        assert actual[key] == pytest.approx(value), (path, key)
    assert '계산 예시' in text and '확률' in text and '구현 근거' in text
    assert '../../README.md#추첨-공식-24종' in text
    assert '../FORMULAS.md' in text


@pytest.mark.parametrize('path', DOCUMENTS, ids=[p.name for p in DOCUMENTS])
def test_local_markdown_links_resolve(path):
    text = path.read_text(encoding='utf-8')
    assert text.count('```') % 2 == 0, f'Unclosed code fence: {path}'
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        linked = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        assert linked.is_relative_to(ROOT), (path, target)
        assert linked.is_file(), (path, target)
        if parsed.fragment:
            assert linked.suffix == '.md', (path, target)
            headings = re.findall(r'^#{1,6}\s+(.+)$', linked.read_text(encoding='utf-8'), re.MULTILINE)
            anchors = {re.sub(r'[^\w\s-]', '', h.lower()).replace(' ', '-') for h in headings}
            assert unquote(parsed.fragment) in anchors, (path, target)


def load_pure_function(name: str):
    """Execute only the named pure function, not the integration module."""
    node = next(node for node in ANALYSIS.body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
                         names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    namespace = {'math': math, 'Counter': Counter, 'DRAW_SIZE': 6, 'NUMBER_PROBABILITY': 6 / 45}
    exec(compile(ast.fix_missing_locations(module), str(COMPONENT / 'analysis.py'), 'exec'), namespace)
    return namespace[name]


def test_documented_balance_example_matches_actual_function():
    score = load_pure_function('_balance_score')((3, 11, 20, 28, 35, 41))
    assert score == pytest.approx(0.901905, abs=0.000001)
    assert '0.901905' in (GUIDES / 'balance_formula.md').read_text(encoding='utf-8')


def test_documented_delta_example_matches_actual_function():
    score = load_pure_function('_delta_score')((3, 11, 20, 28, 35, 44))
    assert score == pytest.approx(0.865667, abs=0.000001)
    assert '0.865667' in (GUIDES / 'delta_system.md').read_text(encoding='utf-8')


def test_documented_bayesian_transform_matches_actual_function():
    posterior = (60 + 500 * (6 / 45)) / (300 + 500)
    weight = .95 / 45 + .05 * posterior / 6
    assert weight == pytest.approx(0.0224305556)
    assert '0.0224305556' in (GUIDES / 'bayesian_shrinkage.md').read_text(encoding='utf-8')


def test_documented_carryover_table_matches_actual_probability_function():
    probability = load_pure_function('match_probability')
    masses = [probability(k) for k in range(7)]
    text = (GUIDES / 'carryover_formula.md').read_text(encoding='utf-8')
    rows = re.findall(r'^\| ([0-6])개 \| ([0-9.]+) \| ([0-9.]+) \|$', text, re.MULTILINE)
    assert len(rows) == 7
    for k, percent, score in rows:
        assert float(percent) == pytest.approx(masses[int(k)] * 100, abs=0.00000001)
        assert float(score) == pytest.approx(masses[int(k)] / max(masses), abs=0.000000001)
    assert sum(masses) == pytest.approx(1)
