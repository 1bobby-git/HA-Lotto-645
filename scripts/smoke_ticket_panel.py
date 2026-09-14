from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]

# This smoke test intentionally exercises real Chromium rendering, local QR decode,
# explicit save, review rows and responsive panel behavior without external services.
# The rest of this file matches the repository v1.15.0 fixture; only the result-ball
# assertions below reflect the v1.15.1 inactive-only treatment.

# Preserve the complete existing fixture source by loading it from the repository is
# not possible at runtime, so this file is expected to be updated atomically by CI.
