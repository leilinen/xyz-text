from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    work_dir: Path
    temp_dir: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    feishu_app_id: str | None
    feishu_app_secret: str | None
    feishu_share_user_id: str | None
    sensevoice_model_path: str | None
    sensevoice_device: str
    sensevoice_language: str
    log_level: str
    log_output: str
    log_file: str
    summary_max_chars: int
    cleaner_segment_length: int
    cleaner_min_sentence_length: int
    cleaner_paragraph_length: int
    request_timeout: int
    llm_max_retries: int
    llm_retry_delay: float
    llm_max_tokens: int
    llm_timeout: int
    markdown_dir: Path


class ConfigError(RuntimeError):
    pass


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_DEFAULTS = {
    "work_dir": "/tmp/media_tool_work",
    "llm_base_url": None,
    "llm_api_key": None,
    "llm_model": None,
    # Legacy backend fields (auto-mapped to unified fields)
    "llm_backend": "openai",
    "glm_model": "glm-4-air",
    "ollama_base_url": "http://localhost:11434/v1",
    "ollama_model": "qwen3.5:4b",
    "openai_base_url": None,
    "openai_api_key": None,
    "openai_model": None,
    "zhipu_api_key": None,
    "feishu_app_id": None,
    "feishu_app_secret": None,
    "feishu_share_user_id": None,
    "sensevoice_model_path": None,
    "sensevoice_device": "cpu",
    "sensevoice_language": "auto",
    "log_level": "INFO",
    "log_output": "file",
    "log_file": "media_tool.log",
    "summary_max_chars": 12000,
    "cleaner_segment_length": 800,
    "cleaner_min_sentence_length": 20,
    "cleaner_paragraph_length": 400,
    "request_timeout": 30,
    "llm_max_retries": 3,
    "llm_retry_delay": 2.0,
    "llm_max_tokens": 4096,
    "llm_timeout": 120,
    "markdown_dir": "raw",
}

# Mapping from legacy llm_backend to unified LLM config
_BACKEND_PRESETS: dict[str, dict[str, str]] = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
    },
}


def _load_config(config_path: Path = _DEFAULT_CONFIG_PATH) -> dict[str, object]:
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid config file: {config_path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"config file must contain a JSON object: {config_path}")
    return payload


def _get_path(config: dict[str, object], key: str, default: str) -> Path:
    value = config.get(key, default)
    return Path(str(value))


def _get_str(config: dict[str, object], key: str, default: str) -> str:
    value = config.get(key, default)
    return str(value)


def _get_optional_str(config: dict[str, object], key: str) -> str | None:
    value = config.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _get_int(config: dict[str, object], key: str, default: int) -> int:
    value = config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"config field {key!r} must be an integer") from exc


def _get_float(config: dict[str, object], key: str, default: float) -> float:
    value = config.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"config field {key!r} must be a number") from exc


def _get_bool(config: dict[str, object], key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ConfigError(f"config field {key!r} must be a boolean")


def validate_log_output(output: str) -> str:
    normalized = output.strip().lower()
    if normalized not in {"file", "console", "both"}:
        raise ConfigError("log_output must be one of: file, console, both")
    return normalized


def _resolve_llm_config(config: dict[str, object]) -> tuple[str, str, str]:
    """Resolve LLM base_url, api_key, model from config.

    Supports both unified format (llm_base_url/llm_api_key/llm_model) and
    legacy format (llm_backend + backend-specific fields).
    """
    # Unified format takes priority
    base_url = _get_optional_str(config, "llm_base_url")
    api_key = _get_optional_str(config, "llm_api_key") or ""
    model = _get_optional_str(config, "llm_model")

    if base_url and model:
        return base_url, api_key, model

    # Legacy format: resolve from backend-specific fields
    backend = _get_str(config, "llm_backend", _DEFAULTS["llm_backend"])
    preset = _BACKEND_PRESETS.get(backend, {})

    if backend == "zhipu":
        base_url = preset.get("base_url", "https://open.bigmodel.cn/api/paas/v4/")
        api_key = _get_optional_str(config, "zhipu_api_key") or ""
        model = _get_str(config, "glm_model", _DEFAULTS["glm_model"])
    elif backend == "ollama":
        base_url = _get_optional_str(config, "ollama_base_url") or preset.get("base_url", "http://localhost:11434/v1")
        model = _get_optional_str(config, "ollama_model") or _DEFAULTS["ollama_model"]
    else:
        # openai or custom
        base_url = _get_optional_str(config, "openai_base_url") or "https://api.openai.com/v1"
        api_key = _get_optional_str(config, "openai_api_key") or ""
        model = _get_optional_str(config, "openai_model") or "gpt-5"

    return base_url, api_key, model


def get_settings(config_path: Path = _DEFAULT_CONFIG_PATH) -> Settings:
    config = _load_config(config_path)
    work_dir = _get_path(config, "work_dir", _DEFAULTS["work_dir"])
    temp_dir = _get_path(config, "temp_dir", str(work_dir / "tmp"))
    llm_base_url, llm_api_key, llm_model = _resolve_llm_config(config)
    return Settings(
        work_dir=work_dir,
        temp_dir=temp_dir,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        feishu_app_id=_get_optional_str(config, "feishu_app_id"),
        feishu_app_secret=_get_optional_str(config, "feishu_app_secret"),
        feishu_share_user_id=_get_optional_str(config, "feishu_share_user_id"),
        sensevoice_model_path=_get_optional_str(config, "sensevoice_model_path"),
        sensevoice_device=_get_str(config, "sensevoice_device", _DEFAULTS["sensevoice_device"]),
        sensevoice_language=_get_str(config, "sensevoice_language", _DEFAULTS["sensevoice_language"]),
        log_level=_get_str(config, "log_level", _DEFAULTS["log_level"]),
        log_output=validate_log_output(_get_str(config, "log_output", _DEFAULTS["log_output"])),
        log_file=_get_str(config, "log_file", _DEFAULTS["log_file"]),
        summary_max_chars=_get_int(config, "summary_max_chars", _DEFAULTS["summary_max_chars"]),
        cleaner_segment_length=_get_int(config, "cleaner_segment_length", _DEFAULTS["cleaner_segment_length"]),
        cleaner_min_sentence_length=_get_int(config, "cleaner_min_sentence_length", _DEFAULTS["cleaner_min_sentence_length"]),
        cleaner_paragraph_length=_get_int(config, "cleaner_paragraph_length", _DEFAULTS["cleaner_paragraph_length"]),
        request_timeout=_get_int(config, "request_timeout", _DEFAULTS["request_timeout"]),
        llm_max_retries=_get_int(config, "llm_max_retries", _DEFAULTS["llm_max_retries"]),
        llm_retry_delay=_get_float(config, "llm_retry_delay", _DEFAULTS["llm_retry_delay"]),
        llm_max_tokens=_get_int(config, "llm_max_tokens", _DEFAULTS["llm_max_tokens"]),
        llm_timeout=_get_int(config, "llm_timeout", _DEFAULTS["llm_timeout"]),
        markdown_dir=_get_path(config, "markdown_dir", _DEFAULTS["markdown_dir"]),
    )


def configure_logging(settings: Settings | None = None) -> None:
    active = settings or get_settings()
    log_level = getattr(logging, active.log_level.upper(), logging.INFO)
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    output_type = active.log_output.lower()

    if output_type in ("file", "both"):
        # Ensure parent directory exists
        log_file_path = Path(active.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(active.log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    if output_type in ("console", "both"):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)


def ensure_runtime_dirs(settings: Settings | None = None) -> Settings:
    active = settings or get_settings()
    active.work_dir.mkdir(parents=True, exist_ok=True)
    active.temp_dir.mkdir(parents=True, exist_ok=True)
    return active


def require_feishu_credentials(settings: Settings | None = None) -> tuple[str, str]:
    active = settings or get_settings()
    if not active.feishu_app_id or not active.feishu_app_secret:
        raise ConfigError("feishu_app_id and feishu_app_secret are required for Feishu integration")
    return active.feishu_app_id, active.feishu_app_secret
