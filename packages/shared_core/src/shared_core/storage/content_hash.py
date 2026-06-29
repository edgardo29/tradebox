"""Content hash helpers for stored objects."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 hex digest for bytes."""
    return sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    """Return the SHA-256 hex digest for UTF-8 text."""
    return sha256_bytes(content.encode("utf-8"))


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 hex digest for a file read in chunks."""
    digest = sha256()
    with Path(path).open("rb") as file:
        for chunk in _read_chunks(file, chunk_size=chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _read_chunks(file: object, *, chunk_size: int) -> Iterable[bytes]:
    while True:
        chunk = file.read(chunk_size)
        if not chunk:
            return
        yield chunk
