#!/usr/bin/env python3
"""Build high-density variants from the canonical Home Assistant brand PNGs.

``brand/logo.png`` and ``brand/icon.png`` are the supplied originals. This
script validates and preserves them, then creates only the optional @2x files.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"
SOURCE_LOGO = BRAND / "logo.png"
SOURCE_ICON = BRAND / "icon.png"


def resize_logo(source: Image.Image, target_height: int) -> Image.Image:
    """Resize the supplied wordmark without changing its aspect ratio."""
    rgba = source.convert("RGBA")
    width = round(rgba.width * target_height / rgba.height)
    return rgba.resize((width, target_height), Image.Resampling.LANCZOS)


def save_png(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, compress_level=9)


def main() -> None:
    for source_path in (SOURCE_LOGO, SOURCE_ICON):
        if not source_path.exists():
            raise RuntimeError(f"missing canonical brand asset: {source_path}")

    source = Image.open(SOURCE_LOGO).convert("RGBA")
    icon = Image.open(SOURCE_ICON).convert("RGBA")
    if source.width <= source.height:
        raise RuntimeError("canonical horizontal logo must be landscape")
    if icon.width != icon.height:
        raise RuntimeError("canonical icon must be square")

    # Preserve the supplied originals and create only optional dense variants.
    save_png(resize_logo(source, 512), BRAND / "logo@2x.png")
    save_png(icon.resize((512, 512), Image.Resampling.LANCZOS), BRAND / "icon@2x.png")

    normal_logo = Image.open(BRAND / "logo.png")
    hidpi_logo = Image.open(BRAND / "logo@2x.png")
    normal_icon = Image.open(BRAND / "icon.png")
    hidpi_icon = Image.open(BRAND / "icon@2x.png")
    assert normal_logo.size == source.size
    assert hidpi_logo.height == 512
    assert normal_icon.size == icon.size
    assert hidpi_icon.size == (512, 512)

    print(f"canonical logo preserved: {source.width}x{source.height}")
    print(f"canonical icon preserved: {icon.width}x{icon.height}")
    print(f"HA logo@2x: {hidpi_logo.width}x{hidpi_logo.height}")
    print("HA icon@2x: 512x512")


if __name__ == "__main__":
    main()
