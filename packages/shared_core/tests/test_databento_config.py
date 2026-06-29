import pytest

from shared_core.config import (
    DatabentoConfig,
    DatabentoConfigError,
    load_databento_config_from_env,
)


def test_databento_config_loads_from_env_mapping() -> None:
    config = load_databento_config_from_env({"DATABENTO_API_KEY": "db-test-key"})

    assert config == DatabentoConfig(api_key="db-test-key")
    assert "db-test-key" not in repr(config)


def test_databento_config_requires_api_key() -> None:
    with pytest.raises(DatabentoConfigError, match="DATABENTO_API_KEY"):
        load_databento_config_from_env({})


def test_databento_config_rejects_placeholder_api_key() -> None:
    with pytest.raises(DatabentoConfigError, match="DATABENTO_API_KEY"):
        load_databento_config_from_env({"DATABENTO_API_KEY": "<api_key>"})
