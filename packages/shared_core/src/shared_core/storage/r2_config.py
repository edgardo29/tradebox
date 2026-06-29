"""Cloudflare R2 configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ


class R2ConfigError(ValueError):
    """Raised when required R2 configuration is missing or invalid."""


@dataclass(frozen=True)
class R2Config:
    """Configuration required to access a private Cloudflare R2 bucket."""

    account_id: str
    access_key_id: str
    secret_access_key: str = field(repr=False)
    bucket_name: str
    endpoint_url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> R2Config:
        source = environ if env is None else env
        values = {
            "account_id": source.get("R2_ACCOUNT_ID", "").strip(),
            "access_key_id": source.get("R2_ACCESS_KEY_ID", "").strip(),
            "secret_access_key": source.get("R2_SECRET_ACCESS_KEY", "").strip(),
            "bucket_name": source.get("R2_BUCKET_NAME", "").strip(),
            "endpoint_url": source.get("R2_ENDPOINT_URL", "").strip().rstrip("/"),
        }

        missing = [
            env_name
            for field_name, env_name in _FIELD_ENV_NAMES.items()
            if _is_missing_or_placeholder(values[field_name])
        ]
        if missing:
            raise R2ConfigError(
                "Missing R2 environment variables: "
                + ", ".join(missing)
                + ". Set them in your local environment or .env before running the R2 smoke test."
            )

        return cls(**values)

    @property
    def s3_endpoint_url(self) -> str:
        """Endpoint URL used by S3-compatible clients."""
        return self.endpoint_url


def load_r2_config_from_env(env: Mapping[str, str] | None = None) -> R2Config:
    """Load R2 config from environment variables."""
    return R2Config.from_env(env)


_FIELD_ENV_NAMES = {
    "account_id": "R2_ACCOUNT_ID",
    "access_key_id": "R2_ACCESS_KEY_ID",
    "secret_access_key": "R2_SECRET_ACCESS_KEY",
    "bucket_name": "R2_BUCKET_NAME",
    "endpoint_url": "R2_ENDPOINT_URL",
}


def _is_missing_or_placeholder(value: str) -> bool:
    return not value or "<" in value or ">" in value
