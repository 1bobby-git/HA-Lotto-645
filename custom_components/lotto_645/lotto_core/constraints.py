"""Strict, bounded conditional-uniform 6/45 generation (not prediction)."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
from math import comb
import re
from secrets import SystemRandom

NUMBERS = tuple(range(1, 46))
PRIMES = frozenset((2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43))
EXACT_LIMIT = 20_000
ATTEMPT_LIMIT = 12_000
RULES_KEY = 'generation_rules'


class ConstraintError(ValueError):
    """Distinguish invalid input, proven empty space and incomplete search."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def numbers(value, *, maximum=45):
    if isinstance(value, str):
        if len(value) > 200:
            raise ConstraintError('invalid_rules', '번호 입력이 너무 깁니다')
        parts = re.split(r'[\s,·]+', value.strip()) if value.strip() else []
        if any(not re.fullmatch(r'[0-9]{1,2}', x) for x in parts):
            raise ConstraintError('invalid_rules', '번호는 공백 또는 쉼표로 구분한 1~45 정수여야 합니다')
        value = [int(x) for x in parts]
    if (not isinstance(value, (list, tuple)) or len(value) > maximum
            or any(type(n) is not int or n not in NUMBERS for n in value)
            or len(set(value)) != len(value)):
        raise ConstraintError('invalid_rules', '번호 범위·개수 또는 중복을 확인하세요')
    return tuple(sorted(value))


def bounds(value, lo, hi):
    if isinstance(value, str):
        if len(value) > 20 or not re.fullmatch(r'\s*[0-9]+(?:\s*[-~]\s*[0-9]+)?\s*', value):
            raise ConstraintError('invalid_rules', '범위는 2-4 또는 3처럼 입력하세요')
        value = tuple(map(int, re.split(r'\s*[-~]\s*', value.strip())))
        if len(value) == 1:
            value = (value[0], value[0])
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(n) is not int for n in value) or not lo <= value[0] <= value[1] <= hi):
        raise ConstraintError('invalid_rules', '조건 범위의 최솟값과 최댓값을 확인하세요')
    return tuple(value)


@dataclass(frozen=True)
class Rules:
    fixed: tuple[int, ...] = ()
    excluded: tuple[int, ...] = ()
    total: tuple[int, int] = (21, 255)
    odd: tuple[int, int] = (0, 6)
    low: tuple[int, int] = (0, 6)
    carryover: tuple[int, int] = (0, 6)
    neighbors: tuple[int, int] = (0, 6)
    primes: tuple[int, int] = (0, 6)
    multiples3: tuple[int, int] = (0, 6)
    max_same_ending: int = 5
    max_run: int = 6
    ac_min: int = 0

    @classmethod
    def parse(cls, value=None):
        if value is None:
            return cls()
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ConstraintError('invalid_rules', '지원하지 않는 조건 설정입니다')
        data = asdict(cls())
        for key, raw in value.items():
            if key in ('fixed', 'excluded'):
                data[key] = numbers(raw, maximum=6 if key == 'fixed' else 45)
            elif key in ('max_same_ending', 'max_run', 'ac_min'):
                if type(raw) is not int or not (0 if key == 'ac_min' else 1) <= raw <= {'max_same_ending': 5, 'max_run': 6, 'ac_min': 10}[key]:
                    raise ConstraintError('invalid_rules', '형태 조건의 정수 범위를 확인하세요')
                data[key] = raw
            else:
                data[key] = bounds(raw, 21 if key == 'total' else 0, 255 if key == 'total' else 6)
        result = cls(**data)
        result.check_feasible()
        return result

    @property
    def pool(self):
        return tuple(n for n in NUMBERS if n not in self.fixed and n not in self.excluded)

    def check_feasible(self, previous=None):
        if set(self.fixed) & set(self.excluded):
            raise ConstraintError('conflicting_rules', '고정번호와 제외번호가 겹칩니다')
        k = 6 - len(self.fixed)
        pool = self.pool
        if len(pool) < k:
            raise ConstraintError('infeasible_rules', '제외 후 남은 후보가 6개보다 적습니다')
        smallest = sum(self.fixed) + sum(pool[:k])
        largest = sum(self.fixed) + (sum(pool[-k:]) if k else 0)
        if self.total[1] < smallest or self.total[0] > largest:
            raise ConstraintError('infeasible_rules', '고정·제외번호로 가능한 합계와 합계 조건이 겹치지 않습니다')
        groups = {'odd': {n for n in NUMBERS if n % 2}, 'low': set(range(1, 23)),
                  'primes': PRIMES, 'multiples3': {n for n in NUMBERS if n % 3 == 0}}
        if previous is not None:
            groups.update(carryover=set(previous), neighbors=neighbor_set(previous))
        for key, group in groups.items():
            fixed_count = len(set(self.fixed) & group)
            available = len(set(pool) & group)
            minimum = fixed_count + max(0, k - (len(pool) - available))
            maximum = fixed_count + min(k, available)
            lo, hi = getattr(self, key)
            if hi < minimum or lo > maximum:
                raise ConstraintError('infeasible_rules', f'{LABELS[key]} 조건과 고정·제외번호가 충돌합니다')


def neighbor_set(previous):
    # Strict +/-1 inside 1..45. A prior number is not its own neighbour.
    return {n + d for n in previous for d in (-1, 1) if 1 <= n + d <= 45} - set(previous)


LABELS = {'total': '합계', 'odd': '홀수 개수', 'low': '1~22 개수', 'carryover': '이월수 개수',
          'neighbors': '이웃수 개수', 'primes': '소수 개수', 'multiples3': '3배수 개수'}


def violations(ticket, rules, previous=()):
    ticket = numbers(ticket, maximum=6)
    if len(ticket) != 6:
        raise ConstraintError('invalid_ticket', '본번호는 중복 없는 6개여야 합니다')
    s = set(ticket)
    bad = []
    if not set(rules.fixed) <= s:
        bad.append('고정번호 누락')
    if s & set(rules.excluded):
        bad.append('제외번호 포함')
    groups = {'total': sum(ticket), 'odd': sum(n % 2 for n in ticket), 'low': sum(n <= 22 for n in ticket),
              'carryover': len(s & set(previous)), 'neighbors': len(s & neighbor_set(previous)),
              'primes': len(s & PRIMES), 'multiples3': sum(n % 3 == 0 for n in ticket)}
    for key, count in groups.items():
        lo, hi = getattr(rules, key)
        if not lo <= count <= hi:
            bad.append(f'{LABELS[key]} {count} (허용 {lo}~{hi})')
    if max(Counter(n % 10 for n in ticket).values()) > rules.max_same_ending:
        bad.append('같은 끝수 개수 초과')
    longest = run = 1
    for a, b in zip(ticket, ticket[1:]):
        run = run + 1 if b == a + 1 else 1
        longest = max(longest, run)
    if longest > rules.max_run:
        bad.append('최대 연속 길이 초과')
    if len({b - a for a, b in combinations(ticket, 2)}) - 5 < rules.ac_min:
        bad.append('AC 최솟값 미달')
    return bad


def generate(rules=None, *, previous=(), blocked=(), rng=None, checkpoint=None,
             attempt_limit=ATTEMPT_LIMIT):
    """Reservoir sample small spaces; otherwise iid rejection without fallback.

    On success each allowed ticket is equally likely, including under the
    finite proposal cap. Exhausting iid trials is not proof of infeasibility.
    """
    from .sampling import fisher_yates
    rules = rules if isinstance(rules, Rules) else Rules.parse(rules)
    previous = numbers(previous, maximum=6)
    rules.check_feasible(previous)
    rng = rng if rng is not None else SystemRandom()
    blocked = {tuple(sorted(row)) for row in blocked}
    pool, k = rules.pool, 6 - len(rules.fixed)
    total = comb(len(pool), k)
    exact = total <= EXACT_LIMIT
    limit = total if exact else attempt_limit
    chosen, allowed = None, 0
    for i, extra in enumerate(combinations(pool, k) if exact else (fisher_yates(pool, k, rng) for _ in range(limit)), 1):
        if checkpoint and (i == 1 or i % 64 == 0):
            checkpoint(i, limit)
        ticket = tuple(sorted((*rules.fixed, *extra)))
        if ticket in blocked or violations(ticket, rules, previous):
            continue
        allowed += 1
        if not exact:
            return ticket
        if rng.randrange(allowed) == 0:
            chosen = ticket
    if chosen is not None:
        return chosen
    if exact:
        raise ConstraintError('infeasible_rules', '모든 후보를 확인했지만 조건을 만족하는 새 조합이 없습니다')
    raise ConstraintError('search_limit', '탐색 한도에 도달했습니다. 불가능하다는 뜻은 아니며 조건을 임의로 완화하지 않았습니다')
