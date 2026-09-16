"""Public condition input validation. No candidate generation is shipped."""
from dataclasses import dataclass, asdict
import re
NUMBERS=tuple(range(1,46))
PRIMES=frozenset((2,3,5,7,11,13,17,19,23,29,31,37,41,43))
RULES_KEY="generation_rules"
class ConstraintError(ValueError):
    def __init__(self,code,message): super().__init__(message); self.code=code

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

