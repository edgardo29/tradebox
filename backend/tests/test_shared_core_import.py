import shared_core


def test_backend_can_import_shared_core() -> None:
    assert shared_core.__version__ == "0.1.0"
