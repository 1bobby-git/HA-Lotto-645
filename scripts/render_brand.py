#!/usr/bin/env python3
"""Build Home Assistant brand assets from the supplied horizontal PNG.

No artwork is redrawn. ``images/logo-horizontal.png`` remains the canonical
horizontal artwork. Home Assistant brand logo variants are only resized from
that PNG to the dimensions required by HA, while icon variants are cropped
from its left lucky-bag component and placed on a transparent square canvas.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"
SOURCE_LOGO = IMAGES / "logo-horizontal.png"


def _occupied_column_runs(alpha: Image.Image) -> list[tuple[int, int]]:
    """Return contiguous x ranges containing visible pixels."""
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
    """Crop the lucky-bag/6/45-ball artwork from the exact horizontal pixels."""
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    runs = _occupied_column_runs(alpha)
    if len(runs) < 2:
        raise RuntimeError("cannot separate lucky-bag icon from horizontal text")

    # The supplied artwork has a transparent gap between the left symbol and
    # the Lotto wordmark. The first occupied run is therefore the exact icon.
    left, right = runs[0]
    component_bbox = alpha.crop((left, 0, right, rgba.height)).getbbox()
    if component_bbox is None:
        raise RuntimeError("lucky-bag component is empty")
    top, bottom = component_bbox[1], component_bbox[3]
    icon = rgba.crop((left, top, right, bottom))

    # Add a small transparent safe area so Home Assistant does not visually
    # clip the balls/bag at rounded-avatar edges. Pixels themselves are not
    # redrawn or altered other than normal high-quality resizing.
    padding = max(1, round(max(icon.size) * 0.06))
    side = max(icon.size) + padding * 2
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(
        icon,
        ((side - icon.width) // 2, (side - icon.height) // 2),
    )
    return square


def resize_logo(source: Image.Image, target_height: int) -> Image.Image:
    """Resize the supplied wordmark without changing its aspect ratio."""
    rgba = source.convert("RGBA")
    width = round(rgba.width * target_height / rgba.height)
    return rgba.resize((width, target_height), Image.Resampling.LANCZOS)


def save_png(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, compress_level=9)


def main() -> None:
    if not SOURCE_LOGO.exists():
        raise RuntimeError(f"missing canonical logo: {SOURCE_LOGO}")

    source = Image.open(SOURCE_LOGO).convert("RGBA")
    if source.width <= source.height:
        raise RuntimeError("canonical horizontal logo must be landscape")

    icon = crop_lucky_bag(source)
    BRAND.mkdir(parents=True, exist_ok=True)

    # Home Assistant brand requirements: logo shortest side <=256 for normal
    # and <=512 for @2x. The full source remains untouched in images/.
    save_png(resize_logo(source, 256), BRAND / "logo.png")
    save_png(resize_logo(source, 512), BRAND / "logo@2x.png")
    save_png(icon.resize((256, 256), Image.Resampling.LANCZOS), BRAND / "icon.png")
    save_png(icon.resize((512, 512), Image.Resampling.LANCZOS), BRAND / "icon@2x.png")
    save_png(icon.resize((512, 512), Image.Resampling.LANCZOS), IMAGES / "icon-square.png")

    normal_logo = Image.open(BRAND / "logo.png")
    hidpi_logo = Image.open(BRAND / "logo@2x.png")
    normal_icon = Image.open(BRAND / "icon.png")
    hidpi_icon = Image.open(BRAND / "icon@2x.png")
    assert normal_logo.height == 256
    assert hidpi_logo.height == 512
    assert normal_icon.size == (256, 256)
    assert hidpi_icon.size == (512, 512)

    print(f"canonical horizontal source preserved: {source.width}x{source.height}")
    print(f"HA logo: {normal_logo.width}x{normal_logo.height}")
    print(f"HA logo@2x: {hidpi_logo.width}x{hidpi_logo.height}")
    print("HA icons: 256x256 / 512x512 (cropped from source)")


if __name__ == "__main__":
    main()
