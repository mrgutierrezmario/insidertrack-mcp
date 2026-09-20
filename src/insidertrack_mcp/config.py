"""Settings, read from the environment (or a ``.env`` file next to the process).

Everything the server needs to know is here: where InsiderTrack is, which
bearer tokens are accepted, whether the one write tool is enabled, and the
caps that keep tool output a sensible size.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration; see ``deploy/.env.example``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    insidertrack_url: str = Field(
        default="http://localhost:8013",
        description="Base URL of the InsiderTrack API (inside the Compose stack: http://app:8003).",
    )
    insidertrack_watchlist_email: str = Field(
        default="", description="Owner's watchlist e-mail on the site (for watchlist_add)."
    )
    insidertrack_watchlist_token: str = Field(
        default="", description="That e-mail's watchlist bearer token (for watchlist_add)."
    )
    mcp_transport: str = Field(
        default="stdio",
        description=(
            "stdio for a local client subprocess; streamable-http to serve over the network."
        ),
    )
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8100
    mcp_path: str = Field(
        default="/",
        description=(
            "Where the MCP endpoint is served. Tailscale serve strips its mount path, so "
            "behind a '/mcp' handler the server still sees '/'. Health is at <path>/health."
        ),
    )
    mcp_tokens: str = Field(
        default="",
        description=(
            "Comma-separated name:token pairs accepted over HTTP, e.g. "
            "'claude-desktop:abc,claude-code:def'. Ignored over stdio."
        ),
    )
    mcp_allow_writes: bool = Field(default=False, description="Enable the watchlist_add tool.")

    @property
    def writes_enabled(self) -> bool:
        """The write tool is registered only with the flag and both watchlist values."""
        return bool(
            self.mcp_allow_writes
            and self.insidertrack_watchlist_email
            and self.insidertrack_watchlist_token
        )

    upstream_timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 60
    max_rows: int = 100
    max_text_chars: int = 4000

    @property
    def tokens(self) -> dict[str, str]:
        """Accepted bearer tokens mapped to the client name they belong to."""
        out: dict[str, str] = {}
        for pair in self.mcp_tokens.split(","):
            name, _, token = pair.strip().partition(":")
            if name and token:
                out[token] = name
        return out


settings = Settings()
