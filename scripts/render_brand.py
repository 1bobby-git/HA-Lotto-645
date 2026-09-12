#!/usr/bin/env python3
"""Validate and derive Home Assistant brand assets from the supplied PNG.

The canonical horizontal artwork is the user's exact PNG. It is never redrawn,
recolored, quantized, cropped or rewritten. Only the square icon is cropped
from the left lucky-bag/6/45 component. Home Assistant's local brand files are
pure size-compatible derivatives of those two canonical assets.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"
SOURCE_LOGO = IMAGES / "logo-horizontal.png"
SQUARE_ICON = IMAGES / "icon-square.png"
EXPECTED_SOURCE_SHA256 = "0fe12c375a418c2bb51d5729526c4c65da70f82f5afecb4ae9ab8f60fe1b2a37"
EXPECTED_SIZE = (2048, 682)
EXPECTED_ICON_SIZE = (550, 550)


def _occupied_column_runs(alpha: Image.Image) -> list[tuple[int, int]]:
    occupied = [
        alpha.crop((x, 0, x + 1, alpha.height)).getbbox() is not None
        for x in range(alpha.width)
    ]
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, present in enumerate(occupied):
        if present and start is None:
            start = x
        elif not present and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, alpha.width))
    return runs


def crop_exact_left_icon(source: Image.Image) -> Image.Image:
    """Crop only the exact left component, then center it on a square canvas."""
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    runs = _occupied_column_runs(alpha)
    if len(runs) < 2:
        raise RuntimeError("cannot separate left icon from horizontal wordmark")
    left, right = runs[0]
    bbox = alpha.crop((left, 0, right, rgba.height)).getbbox()
    if bbox is None:
        raise RuntimeError("left icon is empty")
    top, bottom = bbox[1], bbox[3]
    raw = rgba.crop((left, top, right, bottom))
    side = max(raw.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(raw, ((side - raw.width) // 2, (side - raw.height) // 2))
    return square


def save_png(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, compress_level=9)


def main() -> None:
    data = SOURCE_LOGO.read_bytes()
    digest = sha256(data).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"unexpected horizontal logo bytes: {digest}")

    with Image.open(SOURCE_LOGO) as opened:
        source = opened.convert("RGBA")
    if source.size != EXPECTED_SIZE:
        raise RuntimeError(f"unexpected horizontal logo dimensions: {source.size}")

    icon = crop_exact_left_icon(source)
    if icon.size != EXPECTED_ICON_SIZE:
        raise RuntimeError(f"unexpected square icon dimensions: {icon.size}")
    save_png(icon, SQUARE_ICON)

    # Home Assistant local brand assets: no artistic changes, only resizing.
    BRAND.mkdir(parents=True, exist_ok=True)
    logo_height = 256
    logo_width = round(source.width * logo_height / source.height)
    save_png(source.resize((logo_width, logo_height), Image.Resampling.LANCZOS), BRAND / "logo.png")
    save_png(icon.resize((256, 256), Image.Resampling.LANCZOS), BRAND / "icon.png")

    # Verify the canonical horizontal artwork was never changed by this script.
    if sha256(SOURCE_LOGO.read_bytes()).hexdigest() != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("canonical horizontal logo changed unexpectedly")
    print(f"canonical logo preserved: {source.size}, sha256={digest}")
    print(f"canonical square icon: {icon.size}; HA logo={logo_width}x256; HA icon=256x256")


if __name__ == "__main__":
    main()
