import importlib
import tomllib
from pathlib import Path

import shared_core

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_shared_core_imports() -> None:
    assert shared_core.__version__ == "0.1.0"


def test_foundation_subpackages_import() -> None:
    subpackages = [
        "shared_core.backtesting",
        "shared_core.config",
        "shared_core.market_data.databento",
        "shared_core.market_data",
        "shared_core.models",
        "shared_core.storage",
        "shared_core.strategy",
    ]

    for package_name in subpackages:
        assert importlib.import_module(package_name).__name__ == package_name


def test_pyproject_package_discovery_is_src_based() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "tradebox-shared-core"
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert pyproject["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert pyproject["tool"]["pytest"]["ini_options"]["pythonpath"] == ["src"]
