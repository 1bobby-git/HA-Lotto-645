#!/usr/bin/env python3
"""Validate Lotto brand assets derived from the user-supplied artwork."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"
EXPECTED_LOGO_SHA256 = "d970376a271555cc6654f4daff640c1d9522a8809c077991df5c4ff476585f49"


def main() -> None:
    logo = IMAGES / "logo-horizontal.png"
    icon = IMAGES / "icon-square.png"
    brand_logo = BRAND / "logo.png"
    brand_icon = BRAND / "icon.png"

    digest = sha256(logo.read_bytes()).hexdigest()
    if digest != EXPECTED_LOGO_SHA256:
        raise RuntimeError(f"unexpected horizontal logo: {digest}")
    if brand_logo.read_bytes() != logo.read_bytes():
        raise RuntimeError("integration logo must match canonical horizontal logo")
    if brand_icon.read_bytes() != icon.read_bytes():
        raise RuntimeError("integration icon must match canonical square icon")

    with Image.open(logo) as image:
        if image.size != (384, 128):
            raise RuntimeError(f"unexpected logo dimensions: {image.size}")
    with Image.open(icon) as image:
        if image.size != (256, 256):
            raise RuntimeError(f"unexpected icon dimensions: {image.size}")

    print("validated user-supplied horizontal logo and square crop")


if __name__ == "__main__":
    main()
