"""Compatibility import; implementation lives in the standalone Lotto Core."""
import sys
from .lotto_core import methods as _implementation
globals().update({key: value for key, value in vars(_implementation).items() if not key.startswith("__")})
sys.modules[__name__] = _implementation
