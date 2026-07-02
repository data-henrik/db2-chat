"""
config.py — Application configuration.

Loads settings from a .env file (if present) via python-dotenv and exposes
a single `Config` dataclass instance (`config`) that all modules import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env into the process environment (no-op if the file doesn't exist)
load_dotenv()


@dataclass
class Config:
    # ── IBM Db2 ───────────────────────────────────────────────────────────────
    db2_database: str = field(default_factory=lambda: os.getenv("DB2_DATABASE", ""))
    db2_hostname: str = field(default_factory=lambda: os.getenv("DB2_HOSTNAME", "localhost"))
    db2_port: int = field(default_factory=lambda: int(os.getenv("DB2_PORT", "50000")))
    db2_uid: str = field(default_factory=lambda: os.getenv("DB2_UID", ""))
    db2_pwd: str = field(default_factory=lambda: os.getenv("DB2_PWD", ""))
    # Optional: when set, tool queries default to this schema
    db2_schema: str = field(default_factory=lambda: os.getenv("DB2_SCHEMA", ""))

    # ── Flask ─────────────────────────────────────────────────────────────────
    flask_secret_key: str = field(
        default_factory=lambda: os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    )

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llama3.2")
    )

    @property
    def db2_connection_string(self) -> str:
        """Build a DSN-less ibm_db connection string from the loaded settings."""
        return (
            f"DATABASE={self.db2_database};"
            f"HOSTNAME={self.db2_hostname};"
            f"PORT={self.db2_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.db2_uid};"
            f"PWD={self.db2_pwd};"
        )


# Module-level singleton — import this everywhere:  from config import config
config = Config()
