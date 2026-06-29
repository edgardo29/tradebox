from hashlib import sha256

from shared_core.storage.content_hash import sha256_bytes, sha256_file, sha256_text


def test_sha256_bytes_matches_standard_library() -> None:
    content = b"tradebox smoke partition\n"

    assert sha256_bytes(content) == sha256(content).hexdigest()


def test_sha256_text_encodes_as_utf8() -> None:
    assert sha256_text("tradebox") == sha256(b"tradebox").hexdigest()


def test_sha256_file_hashes_file_contents(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("sample content\n", encoding="utf-8")

    assert sha256_file(path) == sha256(b"sample content\n").hexdigest()
