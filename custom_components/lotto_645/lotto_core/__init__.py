"""Standalone Lotto Core. Importing this package never imports Home Assistant."""
CORE_VERSION = "1.21.0"
API_VERSION = 1
MIN_HISTORY = 30

from .api import describe, generate, generate_json, validate_method_ids

__all__ = ["CORE_VERSION", "API_VERSION", "MIN_HISTORY", "describe", "generate", "generate_json", "validate_method_ids"]
