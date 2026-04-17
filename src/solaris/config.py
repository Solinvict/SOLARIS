# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


@dataclass(slots=True)
class Settings:
    project_root: Path
    db_path: Path
    policies_dir: Path
    default_policy_profile: str
    fts_enabled: bool
    embeddings_enabled: bool
    log_level: str
    adjudication_provider: str
    adjudication_base_url: str
    adjudication_api_key: str
    adjudication_model: str
    adjudication_timeout_seconds: float
    adjudication_prompt_version: str
    divergence_weight_threshold: float
    web_host: str = "127.0.0.1"
    web_port: int = 8766
    web_dev_cors_origin: str = "http://127.0.0.1:5173"
    web_static_dir: Path | None = None
    web_ws_poll_seconds: float = 1.5
    default_scope_tenant: str = "personal"
    default_scope_namespace: str = "solaris"
    default_scope_workspace: str = "default"
    default_scope_project: str = "default"

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        db_path = Path(os.getenv("SOLARIS_DB_PATH", str(project_root / ".runtime" / "solaris.db")))
        if not db_path.is_absolute():
            db_path = project_root / db_path
        policies_dir = Path(os.getenv("SOLARIS_POLICIES_DIR", str(project_root / "policies")))
        if not policies_dir.is_absolute():
            policies_dir = project_root / policies_dir
        web_static_dir = Path(os.getenv("SOLARIS_WEB_STATIC_DIR", str(project_root / "frontend" / "dist")))
        if not web_static_dir.is_absolute():
            web_static_dir = project_root / web_static_dir
        return cls(
            project_root=project_root,
            db_path=db_path,
            policies_dir=policies_dir,
            default_policy_profile=os.getenv("SOLARIS_DEFAULT_POLICY_PROFILE", "default_v1").strip() or "default_v1",
            fts_enabled=_env_bool("SOLARIS_FTS_ENABLED", True),
            embeddings_enabled=_env_bool("SOLARIS_EMBEDDINGS_ENABLED", False),
            log_level=os.getenv("SOLARIS_LOG_LEVEL", "INFO").strip().upper() or "INFO",
            adjudication_provider=os.getenv("SOLARIS_ADJUDICATION_PROVIDER", "off").strip().lower() or "off",
            adjudication_base_url=os.getenv(
                "SOLARIS_ADJUDICATION_BASE_URL",
                os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ).strip(),
            adjudication_api_key=os.getenv(
                "SOLARIS_ADJUDICATION_API_KEY",
                os.getenv("OPENAI_API_KEY", ""),
            ).strip(),
            adjudication_model=os.getenv("SOLARIS_ADJUDICATION_MODEL", "").strip(),
            adjudication_timeout_seconds=_env_float("SOLARIS_ADJUDICATION_TIMEOUT_SECONDS", 20.0),
            adjudication_prompt_version=(
                os.getenv("SOLARIS_ADJUDICATION_PROMPT_VERSION", "solaris_editorial_adjudication_v1").strip()
                or "solaris_editorial_adjudication_v1"
            ),
            divergence_weight_threshold=_env_float("SOLARIS_DIVERGENCE_WEIGHT_THRESHOLD", 0.2),
            web_host=os.getenv("SOLARIS_WEB_HOST", "127.0.0.1").strip() or "127.0.0.1",
            web_port=_env_int("SOLARIS_WEB_PORT", 8766),
            web_dev_cors_origin=os.getenv("SOLARIS_WEB_DEV_CORS_ORIGIN", "http://127.0.0.1:5173").strip()
            or "http://127.0.0.1:5173",
            web_static_dir=web_static_dir,
            web_ws_poll_seconds=max(0.25, _env_float("SOLARIS_WEB_WS_POLL_SECONDS", 1.5)),
            default_scope_tenant=os.getenv("SOLARIS_SCOPE_TENANT", "personal").strip() or "personal",
            default_scope_namespace=os.getenv("SOLARIS_SCOPE_NAMESPACE", "solaris").strip() or "solaris",
            default_scope_workspace=os.getenv("SOLARIS_SCOPE_WORKSPACE", "default").strip() or "default",
            default_scope_project=os.getenv("SOLARIS_SCOPE_PROJECT", "default").strip() or "default",
        )
