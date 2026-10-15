"""Bound the complete inspection body before multipart parsing, including streams."""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image
from starlette import formparsers
from starlette.requests import Request

from .test_duplicate_inspections import UniquePersistence, _setup
from .test_inspections import _metadata

LIMIT = 24 * 1024 * 1024
BOUNDARY = b"kb02-boundary"
CONTENT_TYPE = "multipart/form-data; boundary=kb02-boundary"


def _png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (1, 1), (1, 2, 3)).save(stream, format="PNG")
    return stream.getvalue()


def _part(name: str, content: bytes, filename: str | None = None) -> bytes:
    header = (
        b"--"
        + BOUNDARY
        + b'\r\nContent-Disposition: form-data; name="'
        + name.encode()
        + b'"'
    )
    if filename is not None:
        header += b'; filename="' + filename.encode() + b'"\r\nContent-Type: image/png'
    return header + b"\r\n\r\n" + content + b"\r\n"


def _body(*, size: int | None = None, padding: str = "file") -> bytes:
    prefix = b"".join(
        [
            _part("inspection_id", b"kb02-inspection"),
            _part("metadata", _metadata([0]).encode()),
            _part("virtual_brix", b"13.9"),
            _part("images", _png(), "image.png"),
        ]
    )
    end = b"--" + BOUNDARY + b"--\r\n"
    if size is None:
        return prefix + end
    if padding == "file":
        empty = _part("unused_file", b"", "unused.png")
        payload_size = size - len(prefix) - len(empty) - len(end)
        return prefix + _part("unused_file", b"x" * payload_size, "unused.png") + end
    # Keep each extra field within Starlette's 1MiB per-field limit so that
    # only the aggregate body limit is violated, not another parser rule.
    names = [f"unused_{index}" for index in range(25)]
    remaining = (
        size - len(prefix) - len(end) - sum(len(_part(name, b"")) for name in names)
    )
    parts = [prefix]
    for name in names:
        amount = min(remaining, 1024 * 1024)
        parts.append(_part(name, b"x" * amount))
        remaining -= amount
    assert remaining == 0
    return b"".join(parts) + end


def _send(
    app,
    body: bytes,
    length: str | None,
    *,
    method: str = "POST",
    path: str = "/v1/inspections",
):
    reads = []

    async def chunks() -> AsyncIterator[bytes]:
        for offset in range(0, len(body), 64 * 1024):
            chunk = body[offset : offset + 64 * 1024]
            reads.append(len(chunk))
            yield chunk

    async def run() -> httpx.Response:
        headers = {"content-type": CONTENT_TYPE}
        if length is not None:
            headers["content-length"] = length
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, content=chunks(), headers=headers)

    return asyncio.run(run()), reads


def _app(limit: int = LIMIT):
    setup = _setup(UniquePersistence())
    app = setup[0]
    app.state.settings.inference_max_request_bytes = limit
    service = app.state.inspection_service
    service.inspect = AsyncMock(wraps=service.inspect)
    return setup


def _assert_stopped(setup) -> None:
    app, inference, control, system_images, low_images, late = setup
    app.state.inspection_service.inspect.assert_not_awaited()
    assert inference.calls == 0
    assert control.requests == []
    system_images.save.assert_not_called()
    low_images.save.assert_not_called()
    assert late.active_count == 0


@pytest.mark.parametrize("delta", [-1, 0, 1])
@pytest.mark.parametrize("declared", [True, False])
def test_actual_24mib_multipart_boundaries(delta: int, declared: bool) -> None:
    body = _body(size=LIMIT + delta)
    assert len(body) == LIMIT + delta
    setup = _app()
    response, _ = _send(setup[0], body, str(len(body)) if declared else None)
    assert response.status_code == (413 if delta > 0 else 200)
    if delta > 0:
        _assert_stopped(setup)
    else:
        assert response.json()["decision_reason"] == "NORMAL"
        assert setup[1].calls == len(setup[2].requests) == 1


@pytest.mark.parametrize("length", [None, str(LIMIT), "not-a-number", "-1"])
def test_actual_chunks_override_missing_understated_or_invalid_length(
    length: str | None,
) -> None:
    setup = _app()
    response, _ = _send(setup[0], _body(size=LIMIT + 1), length)
    assert response.status_code == 413
    assert response.json() == {
        "detail": "multipart 요청이 허용된 최대 크기를 초과했습니다"
    }
    _assert_stopped(setup)


def test_overhead_counts_even_when_image_and_known_fields_fit() -> None:
    body = _body()
    known = len(b"kb02-inspection") + len(_metadata([0]).encode()) + len(_png())
    limit = known + 1
    assert known < limit < len(body)
    setup = _app(limit)
    response, _ = _send(setup[0], body, None)
    assert response.status_code == 413
    _assert_stopped(setup)


@pytest.mark.parametrize("padding", ["file", "fields"])
def test_unused_parts_cannot_bypass_complete_body_limit(padding: str) -> None:
    setup = _app()
    response, _ = _send(setup[0], _body(size=LIMIT + 1, padding=padding), None)
    assert response.status_code == 413
    _assert_stopped(setup)


def test_declared_oversize_stops_before_reading_or_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = AsyncMock(side_effect=AssertionError("multipart parser must not run"))
    monkeypatch.setattr(formparsers.MultiPartParser, "parse", parser)
    setup = _app()
    response, reads = _send(setup[0], _body(), str(LIMIT + 1))
    assert response.status_code == 413
    assert reads == []
    parser.assert_not_awaited()
    _assert_stopped(setup)


def test_over_limit_chunk_is_not_parsed_and_partial_uploads_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = []
    parsed = []
    spool = formparsers.SpooledTemporaryFile
    write = formparsers.multipart.MultipartParser.write

    def capture_file(*args, **kwargs):
        file = spool(*args, **kwargs)
        files.append(file)
        return file

    def capture_write(parser, data):
        parsed.append(len(data))
        return write(parser, data)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", capture_file)
    monkeypatch.setattr(formparsers.multipart.MultipartParser, "write", capture_write)
    monkeypatch.setattr(
        Request,
        "body",
        AsyncMock(side_effect=AssertionError("no whole-body buffering")),
    )
    setup = _app()
    response, reads = _send(setup[0], _body(size=LIMIT + 1), None)
    assert response.status_code == 413
    assert sum(reads) == LIMIT + 1
    assert sum(parsed) == LIMIT
    assert len(files) == 2
    assert any(file._rolled for file in files)
    assert all(file.closed for file in files)
    _assert_stopped(setup)


def test_body_limit_is_not_global() -> None:
    setup = _app(1)
    response, _ = _send(setup[0], b"xx", str(LIMIT + 1), method="GET", path="/health")
    assert response.status_code == 200
