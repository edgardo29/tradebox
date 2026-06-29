import shared_core
from dagster import Definitions

import pipelines
from pipelines.assets.spy_raw_to_clean import SPY_RAW_TO_CLEAN_ASSET_NAME
from pipelines.definitions import defs
from pipelines.jobs import safe_market_data_pipeline_job, spy_raw_to_clean_job


def test_pipeline_package_imports() -> None:
    assert pipelines.__version__ == "0.1.0"


def test_dagster_definitions_import() -> None:
    assert isinstance(defs, Definitions)


def test_dagster_definitions_include_spy_raw_to_clean_job() -> None:
    assert defs.get_job_def("spy_raw_to_clean_job").name == "spy_raw_to_clean_job"
    assert spy_raw_to_clean_job.name == "spy_raw_to_clean_job"


def test_dagster_definitions_include_safe_market_data_pipeline_job() -> None:
    assert (
        defs.get_job_def("safe_market_data_pipeline_job").name
        == "safe_market_data_pipeline_job"
    )
    assert safe_market_data_pipeline_job.name == "safe_market_data_pipeline_job"


def test_spy_raw_to_clean_asset_name_is_stable() -> None:
    assert SPY_RAW_TO_CLEAN_ASSET_NAME == "spy_raw_to_clean_existing_sample"


def test_pipeline_can_import_shared_core() -> None:
    assert shared_core.__version__ == "0.1.0"
