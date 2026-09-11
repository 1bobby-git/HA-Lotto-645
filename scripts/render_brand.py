#!/usr/bin/env python3
"""Build Home Assistant brand assets from the user-supplied PNG artwork.

The horizontal logo is the canonical source and is never redrawn.  The square
icon is produced only by cropping the left, non-transparent artwork component
(the lucky-bag symbol) from that exact PNG, padding it to a square canvas, and
resizing it for Home Assistant density variants.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"
SOURCE_LOGO = IMAGES / "logo-horizontal.png"


def _occupied_column_runs(alpha: Image.Image) -> list[tuple[int, int]]:
    """Return contiguous x ranges containing non-transparent pixels."""
    width, height = alpha.size
    occupied = [
        alpha.crop((x, 0, x + 1, height)).getbbox() is not None
        for x in range(width)
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
        runs.append((start, width))
    return runs


def crop_lucky_bag(source: Image.Image) -> Image.Image:
    """Crop the left lucky-bag component from the exact supplied logo pixels."""
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    runs = _occupied_column_runs(alpha)
    if len(runs) < 2:
        raise RuntimeError("cannot separate lucky-bag icon from horizontal text")

    # In the supplied artwork the first non-transparent horizontal component is
    # the complete lucky-bag + 6/45 balls.  Text starts after a transparent gap.
    left, right = runs[0]
    component_alpha = alpha.crop((left, 0, right, rgba.height))
    component_bbox = component_alpha.getbbox()
    if component_bbox is None:
        raise RuntimeError("lucky-bag component is empty")
    top = component_bbox[1]
    bottom = component_bbox[3]
    icon = rgba.crop((left, top, right, bottom))

    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset = ((side - icon.width) // 2, (side - icon.height) // 2)
    square.alpha_composite(icon, offset)
    return square


def save_png(image: Image.Image, target: Path, size: tuple[int, int]) -> None:
    """Resize without redrawing and save a transparent PNG."""
    target.parent.mkdir(parents=True, exist_ok=True)
    output = image.resize(size, Image.Resampling.LANCZOS)
    output.save(target, format="PNG", optimize=True)


def main() -> None:
    if not SOURCE_LOGO.exists():
        raise RuntimeError(f"missing canonical logo: {SOURCE_LOGO}")

    source = Image.open(SOURCE_LOGO).convert("RGBA")
    icon = crop_lucky_bag(source)
    BRAND.mkdir(parents=True, exist_ok=True)

    # Horizontal artwork remains byte-for-byte the user-supplied PNG.
    shutil.copyfile(SOURCE_LOGO, BRAND / "logo.png")
    shutil.copyfile(SOURCE_LOGO, BRAND / "logo@2x.png")

    # Only the left lucky-bag symbol is cropped for square icon assets.
    save_png(icon, BRAND / "icon.png", (256, 256))
    save_png(icon, BRAND / "icon@2x.png", (512, 512))
    save_png(icon, IMAGES / "icon-square.png", (512, 512))

    print(f"canonical logo preserved: {source.width}x{source.height}")
    print(f"cropped lucky-bag source: {icon.width}x{icon.height}")


if __name__ == "__main__":
    main()
