#!/usr/bin/env python3
"""Validate the supplied Lotto logo and derive Home Assistant brand assets.

``images/logo-horizontal.png`` is the user's exact supplied horizontal artwork.
It is NEVER redrawn, cropped, recolored, quantized, or rewritten by this script.
Only the square icon is cropped from the left lucky-bag/6/45 component.  The
Home Assistant integration logo/icon are size-compatible derivatives of those
two canonical images.
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


def _occupied_column_runs(alpha: Image.Image) -> list[tuple[int, int]]:
    """Return contiguous x ranges that contain visible pixels."""
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
    """Crop only the supplied left symbol and center it on a square canvas."""
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    runs = _occupied_column_runs(alpha)
    if len(runs) < 2:
        raise RuntimeError("cannot separate left icon from the Lotto wordmark")
    left, right = runs[0]
    component_bbox = alpha.crop((left, 0, right, rgba.height)).getbbox()
    if component_bbox is None:
        raise RuntimeError("left icon is empty")
    top, bottom = component_bbox[1], component_bbox[3]
    icon = rgba.crop((left, top, right, bottom))

    # No artistic padding or redraw.  Only make the crop square by transparent
    # centering; for the supplied artwork this is 550x464 -> 550x550.
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    return square


def save_lossless(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, compress_level=9)


def main() -> None:
    if not SOURCE_LOGO.exists():
        raise RuntimeError(f"missing user-supplied logo: {SOURCE_LOGO}")
    data = SOURCE_LOGO.read_bytes()
    digest = sha256(data).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"unexpected horizontal logo bytes: {digest}")

    with Image.open(SOURCE_LOGO) as opened:
        source = opened.convert("RGBA")
    if source.size != EXPECTED_SIZE:
        raise RuntimeError(f"unexpected horizontal logo dimensions: {source.size}")

    icon = crop_exact_left_icon(source)
    if icon.size != (550, 550):
        raise RuntimeError(f"unexpected exact icon crop size: {icon.size}")

    # Canonical square asset: exact left crop, no extra padding or redraw.
    save_lossless(icon, SQUARE_ICON)

    # Home Assistant local brand dimensions.  These are pure lossless-source
    # resizes; the artwork itself is unchanged.
    logo_height = 256
    logo_width = round(source.width * logo_height / source.height)
    save_lossless(
        source.resize((logo_width, logo_height), Image.Resampling.LANCZOS),
        BRAND / "logo.png",
    )
    save_lossless(
        icon.resize((256, 256), Image.Resampling.LANCZOS),
        BRAND / "icon.png",
    )

    with Image.open(BRAND / "logo.png") as logo:
        if logo.height != 256:
            raise RuntimeError("invalid HA logo height")
    with Image.open(BRAND / "icon.png") as brand_icon:
        if brand_icon.size != (256, 256):
            raise RuntimeError("invalid HA icon size")

    print(f"exact horizontal logo preserved: {source.size}, sha256={digest}")
    print("canonical square icon: 550x550 exact left-component crop")
    print(f"HA logo: {logo_width}x256; HA icon: 256x256")


if __name__ == "__main__":
    main()
