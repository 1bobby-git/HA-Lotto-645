#!/usr/bin/env python3
"""Render Home Assistant local brand PNGs from the canonical SVG artwork."""

from __future__ import annotations

from pathlib import Path
import struct

import cairosvg

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
BRAND = ROOT / "custom_components" / "lotto_645" / "brand"


def render(source: Path, target: Path, width: int, height: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        url=str(source),
        write_to=str(target),
        output_width=width,
        output_height=height,
    )


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not a PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def main() -> None:
    logo_svg = IMAGES / "logo-horizontal.svg"
    icon_svg = IMAGES / "icon-square.svg"

    outputs = (
        (logo_svg, BRAND / "logo.png", 683, 256),
        (logo_svg, BRAND / "logo@2x.png", 1365, 512),
        (icon_svg, BRAND / "icon.png", 256, 256),
        (icon_svg, BRAND / "icon@2x.png", 512, 512),
        (logo_svg, IMAGES / "logo-horizontal.png", 683, 256),
        (icon_svg, IMAGES / "icon-square.png", 256, 256),
    )
    for source, target, width, height in outputs:
        render(source, target, width, height)
        actual = png_size(target)
        if actual != (width, height):
            raise RuntimeError(f"unexpected PNG size for {target}: {actual}")
        print(f"rendered {target.relative_to(ROOT)}: {width}x{height}")


if __name__ == "__main__":
    main()
