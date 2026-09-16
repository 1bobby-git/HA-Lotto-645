"""Budget-fixed, read-only portfolios with explicitly conditional verification."""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import comb
from secrets import SystemRandom

from .constraints import ConstraintError, Rules, numbers, violations

MODES = ('balanced', 'coverage', 'wheel9')
CANDIDATE_LIMIT = 4096
VERIFY_LIMIT = 20_000


def metrics(tickets, pool):
    groups = {size: {part for row in tickets for part in combinations(row, size)} for size in (1, 2, 3)}
    usage = Counter(n for row in tickets for n in row)
    return {'number_coverage': len(groups[1]), 'pair_coverage': len(groups[2]),
            'triple_coverage': len(groups[3]), 'candidate_count': len(pool),
            'number_usage': {str(n): usage[n] for n in pool},
            'maximum_overlap': max((len(set(a) & set(b)) for a, b in combinations(tickets, 2)), default=0)}


def verify(tickets, pool, checkpoint=None):
    """Exact minimum of the best ticket, conditional on r hits in this pool."""
    sizes = tuple(r for r in range(1, 7) if r <= len(pool) and 6-r <= 45-len(pool))
    cases = sum(comb(len(pool), r) for r in sizes)
    if cases > VERIFY_LIMIT:
        return {'verification_complete': False, 'conditional_min_match': {},
                'verification_cases': 0, 'verification_reason': 'candidate_space_limit',
                'counterexample_count': None}
    result = {}
    done = 0
    sets = [set(row) for row in tickets]
    for r in sizes:
        minimum = 6
        for hit in combinations(pool, r):
            done += 1
            if checkpoint and done % 128 == 0:
                checkpoint(done, cases)
            minimum = min(minimum, max(len(set(hit) & row) for row in sets))
        result[str(r)] = minimum
    return {'verification_complete': True, 'conditional_min_match': result,
            'verification_cases': done, 'verification_reason': 'exhaustive_conditional_sets',
            'counterexample_count': 0}


def generate_portfolio(candidates, ticket_count=5, *, mode='balanced', rules=None,
                       previous=(), blocked=(), max_overlap=6, rng=None, checkpoint=None):
    """Produce all requested games or a typed failure; never increase the budget."""
    from .sampling import fisher_yates
    pool = numbers(candidates)
    if len(pool) < 6:
        raise ConstraintError('invalid_pool', '후보번호를 6개 이상 선택하세요')
    if type(ticket_count) is not int or not 1 <= ticket_count <= 5:
        raise ConstraintError('invalid_count', '게임 수는 1~5개입니다')
    if mode not in MODES or type(max_overlap) is not int or not 0 <= max_overlap <= 6:
        raise ConstraintError('invalid_mode', '조합 설계 방식과 중복 한도를 확인하세요')
    rules = rules if isinstance(rules, Rules) else Rules.parse(rules)
    previous = numbers(previous, maximum=6)
    if not set(rules.fixed) <= set(pool):
        raise ConstraintError('invalid_pool', '후보군에 모든 고정번호가 있어야 합니다')
    if len(rules.fixed) > max_overlap and ticket_count > 1:
        raise ConstraintError('conflicting_rules', '고정번호 수가 게임 간 중복 한도보다 큽니다')
    blocked = {tuple(sorted(row)) for row in blocked}
    rng = rng if rng is not None else SystemRandom()
    if mode == 'wheel9':
        if len(pool) != 9 or ticket_count != 3:
            raise ConstraintError('invalid_wheel', '9후보 휠링은 후보 9개와 정확히 3게임이 필요합니다')
        # 9!/(3!^3*3!) = 280 partitions, checked exactly. Each game omits a block.
        choices = []
        first = pool[0]
        for step, rest_a in enumerate(combinations(pool[1:], 2), 1):
            if checkpoint:
                checkpoint(step, 28)
            a = (first, *rest_a)
            remaining = tuple(n for n in pool if n not in a)
            for rest_b in combinations(remaining[1:], 2):
                b = (remaining[0], *rest_b)
                c = tuple(n for n in remaining if n not in b)
                rows = [tuple(n for n in pool if n not in group) for group in (a, b, c)]
                if (all(row not in blocked and not violations(row, rules, previous) for row in rows)
                        and all(len(set(x) & set(y)) <= max_overlap for x, y in combinations(rows, 2))):
                    choices.append(rows)
        if not choices:
            raise ConstraintError('infeasible_rules', '설정한 조건과 제외 조합을 모두 지키는 9후보 휠링이 없습니다')
        selected = choices[rng.randrange(len(choices))]
    else:
        pool = tuple(n for n in pool if n not in rules.excluded)
        if len(pool) < 6:
            raise ConstraintError('infeasible_rules', '제외 후 후보가 6개보다 적습니다')
        variable = tuple(n for n in pool if n not in rules.fixed)
        k = 6 - len(rules.fixed)
        exact = comb(len(variable), k) <= CANDIDATE_LIMIT
        proposals = combinations(variable, k) if exact else (fisher_yates(variable, k, rng) for _ in range(CANDIDATE_LIMIT))
        allowed = set()
        for i, extra in enumerate(proposals, 1):
            if checkpoint and i % 128 == 0:
                checkpoint(i, CANDIDATE_LIMIT)
            row = tuple(sorted((*rules.fixed, *extra)))
            if row not in blocked and not violations(row, rules, previous):
                allowed.add(row)
        if len(allowed) < ticket_count:
            raise ConstraintError('infeasible_rules' if exact else 'search_limit',
                                  '조건을 지키는 요청 게임 수를 확보하지 못했습니다. 게임 수나 조건을 임의로 바꾸지 않았습니다')
        selected = []
        for _ in range(ticket_count):
            possible = sorted(row for row in allowed if all(len(set(row) & set(old)) <= max_overlap for old in selected))
            if not possible:
                # Greedy dead end is not a mathematical impossibility proof.
                raise ConstraintError('search_limit', '중복 한도를 지키는 조합 묶음을 찾지 못했습니다. 조건을 완화하지 않았습니다')
            used = Counter(n for row in selected for n in row)
            triples = {part for row in selected for part in combinations(row, 3)}
            def score(row):
                balance = -sum((used[n] + 1) ** 2 - used[n] ** 2 for n in row)
                novel = sum(t not in triples for t in combinations(row, 3))
                return (balance, novel) if mode == 'balanced' else (novel, balance)
            best = max(map(score, possible))
            tied = [row for row in possible if score(row) == best]
            row = tied[rng.randrange(len(tied))]
            selected.append(row)
            allowed.remove(row)
    verification = verify(selected, pool, checkpoint)
    return {'formula_id': 'portfolio_coverage', 'formula_version': 1, 'mode': mode,
            'candidate_numbers': list(pool), 'tickets': [list(row) for row in selected],
            'ticket_count': ticket_count, 'saved_as_purchase': False,
            'global_optimality_proven': False, 'constraints_satisfied': True,
            **metrics(selected, pool), **verification,
            'notice': '요청한 게임 수만 생성한 미구매 미리보기입니다. 조건부 최소 일치는 후보군에 본번호가 해당 개수 포함되고 모든 게임을 유지할 때만 적용됩니다. 후보 적중·1등·수익을 보장하지 않습니다.'}
