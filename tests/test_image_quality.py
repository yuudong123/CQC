from __future__ import annotations

import io
import struct
import unittest
import zlib

from src.data.image_quality import PngValidationError, validate_png_stream


def _chunk(name: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(name)
    checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)


def _png() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 2, 3, 8, 2, 0, 0, 0)
    scanlines = b"\x00" + b"\x00" * 6 + b"\x00" + b"\x00" * 6 + b"\x00" + b"\x00" * 6
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(scanlines)) + _chunk(b"IEND", b"")


class ImageQualityTest(unittest.TestCase):
    def test_validates_complete_png(self) -> None:
        value = _png()
        sha256, width, height = validate_png_stream(io.BytesIO(value))
        self.assertEqual((2, 3), (width, height))
        self.assertEqual(64, len(sha256))

    def test_rejects_corrupt_chunk_crc(self) -> None:
        value = bytearray(_png())
        value[-1] ^= 0xFF
        with self.assertRaises(PngValidationError):
            validate_png_stream(io.BytesIO(value))

    def test_rejects_truncated_png(self) -> None:
        with self.assertRaises(PngValidationError):
            validate_png_stream(io.BytesIO(_png()[:-5]))


if __name__ == "__main__":
    unittest.main()
