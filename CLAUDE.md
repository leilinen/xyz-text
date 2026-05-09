# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Media Transcript Skill — automatically transcribes and summarizes media links from Bilibili, YouTube, and Xiaoyuzhou. Uses a modular "platform adapter + capability modules + orchestration" architecture. Consumed via CLI or as an OpenClaw Skill.

**Core workflow:**
1. Identify platform via adapter registry
2. Extract subtitles (via `yt-dlp`) or fall back to ASR (audio download + SenseVoice transcription)
3. Clean and segment transcript
4. Generate structured summary (via pluggable LLM backend: Zhipu / Ollama / OpenAI-compatible)
5. Fetch hot comments (YouTube/Bilibili)
6. Optionally publish to Feishu
7. Output unified JSON result

## Architecture

### Platform Adapter Pattern
- `src/media_tool/platforms/base.py` — Abstract `PlatformAdapter` class
- `src/media_tool/platforms/registry.py` — Registry pattern for platform resolution
- Adapters for: Bilibili, YouTube, Xiaoyuzhou
- **To add a new platform:** Create adapter in `platforms/`, inherit from `PlatformAdapter`, implement `matches()`, register in `registry.py`. No changes needed elsewhere.

### LLM Backend Abstraction
- `src/media_tool/llm.py` — `LLMClient` protocol with `complete(messages, temperature) -> str`
- Three backends: `ZhipuClient`, `OllamaClient` (native API, thinking disabled), `OpenAIClient`
- `RetryingClient` wraps any backend with exponential backoff (`llm_max_retries` / `llm_retry_delay`)
- **To add a new LLM backend:** Create class implementing `LLMClient` protocol, add branch in `create_llm_client()`, add config fields in `config.py`. `summarizer.py` and other callers need no changes.

### Data Models
- `src/media_tool/models.py` — Frozen dataclasses: `MediaSource`, `SubtitleResult`, `TranscriptResult`, `SummaryResult`, `Comment`, `HotCommentsResult`, `FeishuDocResult`, `ProcessResult`
- All modules share these types; no ad-hoc dicts flow through the pipeline.

### Module Organization
- `pipeline.py` — Main orchestration (`process_media()`), shared by CLI and Skill
- `platforms/` — Platform recognition, URL normalization, yt-dlp parameter strategies
- `subtitles.py` — Subtitle extraction and video metadata via yt-dlp
- `asr.py` — Audio download and ASR via SenseVoice
- `cleaner.py` — Text cleaning, sentence segmentation, paragraph splitting
- `summarizer.py` — LLM structured summary + punctuation correction
- `llm.py` — LLM backend abstraction with retry (see above)
- `comments.py` — Hot comment extraction for YouTube (yt-dlp) and Bilibili (direct API), with pin/favorite/like-based filtering
- `feishu.py` — Feishu document API wrapper + notifications
- `storage.py` — Local JSON result persistence + Feishu retry from saved results
- `config.py` — Settings dataclass, `config.json` loading, validation, logging setup

### Entry Points
- `media_processor.py` — Standalone CLI script (run from repo root)
- `media_transcript_skill.py` — OpenClaw Skill thin wrapper (spawns subprocess)
- `skills/media-transcript/SKILL.md` — OpenClaw skill definition

## Common Commands

### Running the CLI
```bash
python3 media_processor.py "https://www.youtube.com/watch?v=abc123"
python3 media_processor.py "URL" --no-feishu      # skip Feishu
python3 media_processor.py "URL" --no-cleanup      # keep temp files
python3 media_processor.py "URL" --no-summary      # skip AI summary
python3 media_processor.py "URL" -o transcript.txt # save transcript to file
python3 media_processor.py --retry result.json     # retry Feishu upload
```

**Important:** Always run from repository root so `media_processor.py` can resolve local imports from `src/`.

### Running Tests
```bash
pytest tests/                                          # all tests
pytest tests/test_platform_registry.py                 # specific file
pytest tests/test_platform_registry.py::test_resolve_known_platforms  # specific test
```

### Dependencies
- Python 3.9+, `ffmpeg`, `yt-dlp`
- Python packages: `yt-dlp`, `ffmpeg-python`, `zhipuai`, `requests`, `pytest`
- For ASR: `pip install funasr torchaudio modelscope`

## Configuration

All configuration via `config.json` in repository root. No environment variables.

**Key fields:**
- `llm_backend`: `"zhipu"` (default), `"ollama"`, or `"openai"` — selects LLM backend
- `zhipu_api_key`: Required when `llm_backend` is `"zhipu"`
- `openai_api_key` / `openai_base_url` / `openai_model`: Required when `llm_backend` is `"openai"`
- `feishu_app_id` / `feishu_app_secret`: Required for Feishu publishing

See `config.py` for all fields and validation logic.

## Data Flow

1. **Platform resolution** (`registry.py`) → Adapter with URL normalization
2. **Subtitle extraction** (`subtitles.py`) via yt-dlp with platform-specific args
3. **ASR fallback** (`asr.py`) → Audio download via yt-dlp, then SenseVoice transcription
4. **Text processing** (`cleaner.py`) → Clean, fix punctuation (via LLM if needed), segment
5. **Summarization** (`summarizer.py`) → LLM structured summary via `llm.py` backend
6. **Comments** (`comments.py`) → Fetch hot comments for YouTube/Bilibili
7. **Publishing** (`feishu.py`) → Optional Feishu document creation + notifications
8. **Storage** (`storage.py`) → Persist result as JSON for retry

All artifacts stored in per-run temp directories under `work_dir/tmp/{platform}/{run_id}/`.

## Error Handling

- `MediaToolError` base class for domain errors
- `ConfigError` for configuration issues
- `ASRError` for transcription failures
- `FeishuAPIError` for Feishu integration issues
- `UnsupportedPlatformError` for unknown platforms

CLI and Skill entry points catch exceptions and return structured JSON errors with `ok: false`.
