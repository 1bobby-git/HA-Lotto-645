#!/usr/bin/env python3
"""Validate the user's Lotto artwork and derive only the square icon.

The horizontal logo is the user's supplied artwork with resolution normalization
only. It is never redrawn, recolored, quantized or cropped. The square icon is
the only crop: the left lucky-bag + 6/45 symbol centered on transparent square.
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
EXPECTED_SOURCE_SHA256 = "fc220ddd9a82111dc3a620562090e884f1ee9e697421a3257db734bf206b688a"
EXPECTED_SIZE = (768, 256)
EXPECTED_RAW_ICON_SIZE = (207, 175)


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


def crop_left_icon(source: Image.Image) -> Image.Image:
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
    if raw.size != EXPECTED_RAW_ICON_SIZE:
        raise RuntimeError(f"unexpected left crop dimensions: {raw.size}")
    side = max(raw.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(raw, ((side - raw.width) // 2, (side - raw.height) // 2))
    return square.resize((256, 256), Image.Resampling.LANCZOS)


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

    icon = crop_left_icon(source)
    save_png(icon, SQUARE_ICON)

    # HA uses the same horizontal PNG bytes and same square icon bytes.
    BRAND.mkdir(parents=True, exist_ok=True)
    (BRAND / "logo.png").write_bytes(data)
    (BRAND / "icon.png").write_bytes(SQUARE_ICON.read_bytes())

    if SOURCE_LOGO.read_bytes() != (BRAND / "logo.png").read_bytes():
        raise RuntimeError("HA horizontal logo differs from canonical logo")
    if SQUARE_ICON.read_bytes() != (BRAND / "icon.png").read_bytes():
        raise RuntimeError("HA square icon differs from canonical crop")
    print(f"horizontal artwork preserved: {source.size}, sha256={digest}")
    print("square icon: exact left component crop -> 256x256")


if __name__ == "__main__":
    main()
