"""One JSON request per invocation. No network, result evaluation, or persistence."""
import argparse
import json
import sys
from . import API_VERSION, describe
from .api import generate_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Lotto Core generation API')
    parser.add_argument('--describe', action='store_true', help='Print the versioned formula catalog')
    args = parser.parse_args()
    try:
        if args.describe:
            result = describe()
        else:
            raw = sys.stdin.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError('입력 크기 제한 초과')
            request = json.loads(raw)
            if not isinstance(request, dict) or (type(request.get('api_version')) is not int or request.get('api_version') != API_VERSION):
                raise ValueError('지원하지 않는 API 버전')
            allowed = {'api_version','history','method_ids','target_round','generation_nonce','formula_options','saju_profile'}
            if set(request) - allowed:
                raise ValueError('지원하지 않는 입력 필드')
            request.pop('api_version')
            result = generate_json(**request)
        json.dump(result, sys.stdout, ensure_ascii=False, allow_nan=False)
        sys.stdout.write('\n')
        return 0
    except (KeyError, TypeError, ValueError) as exc:
        # Never echo profile data or a Python traceback into a calling app's log.
        json.dump({'error': {'code': getattr(exc, 'code', 'invalid_input'),
                             'message': '입력·공식 조건 또는 API 버전을 확인하세요.'}}, sys.stdout, ensure_ascii=False)
        sys.stdout.write('\n')
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
