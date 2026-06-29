import pytest

from shared_core.storage.r2_config import R2Config, R2ConfigError, load_r2_config_from_env


def test_r2_config_loads_from_env_mapping() -> None:
    config = load_r2_config_from_env(
        {
            "R2_ACCOUNT_ID": "abc123",
            "R2_ACCESS_KEY_ID": "access-key",
            "R2_SECRET_ACCESS_KEY": "secret-key",
            "R2_BUCKET_NAME": "tradebox-dev-market-data",
            "R2_ENDPOINT_URL": "https://abc123.r2.cloudflarestorage.com/",
        }
    )

    assert config == R2Config(
        account_id="abc123",
        access_key_id="access-key",
        secret_access_key="secret-key",
        bucket_name="tradebox-dev-market-data",
        endpoint_url="https://abc123.r2.cloudflarestorage.com",
    )
    assert config.s3_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_r2_config_requires_all_env_vars() -> None:
    with pytest.raises(R2ConfigError) as exc_info:
        load_r2_config_from_env({})

    message = str(exc_info.value)
    assert "R2_ACCOUNT_ID" in message
    assert "R2_ACCESS_KEY_ID" in message
    assert "R2_SECRET_ACCESS_KEY" in message
    assert "R2_BUCKET_NAME" in message
    assert "R2_ENDPOINT_URL" in message


def test_r2_config_rejects_placeholder_endpoint() -> None:
    with pytest.raises(R2ConfigError, match="R2_ENDPOINT_URL"):
        load_r2_config_from_env(
            {
                "R2_ACCOUNT_ID": "abc123",
                "R2_ACCESS_KEY_ID": "access-key",
                "R2_SECRET_ACCESS_KEY": "secret-key",
                "R2_BUCKET_NAME": "tradebox-dev-market-data",
                "R2_ENDPOINT_URL": "https://<account_id>.r2.cloudflarestorage.com",
            }
        )
