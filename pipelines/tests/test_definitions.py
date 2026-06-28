import shared_core
from dagster import Definitions

import pipelines
from pipelines.definitions import defs


def test_pipeline_package_imports() -> None:
    assert pipelines.__version__ == "0.1.0"


def test_dagster_definitions_import() -> None:
    assert isinstance(defs, Definitions)


def test_pipeline_can_import_shared_core() -> None:
    assert shared_core.__version__ == "0.1.0"
