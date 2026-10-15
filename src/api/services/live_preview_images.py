"""Build small, transient dashboard images without changing inference inputs."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO

from PIL import Image, ImageOps


def build_live_previews(
    images: Sequence[bytes], *, max_dimension: int, jpeg_quality: int
) -> list[tuple[bytes, str]]:
    """Preserve input order and orientation while encoding JPEG previews in memory."""

    previews: list[tuple[bytes, str]] = []
    for content in images:
        with Image.open(BytesIO(content)) as source:
            oriented = ImageOps.exif_transpose(source)
            oriented.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            if oriented.mode in {"RGBA", "LA"} or (
                oriented.mode == "P" and "transparency" in oriented.info
            ):
                rgba = oriented.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                preview = background
            else:
                preview = oriented.convert("RGB")
            output = BytesIO()
            preview.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
            previews.append((output.getvalue(), "image/jpeg"))
    return previews
