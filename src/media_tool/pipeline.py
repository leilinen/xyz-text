from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .asr import extract_audio_and_transcribe
from .cleaner import clean_transcript_text, split_segments
from .comments import fetch_comments
from .config import configure_logging, ensure_runtime_dirs, get_settings
from .feishu import notify_failure, notify_start, notify_success, publish_summary
from .markdown import save_markdown
from .models import MediaSource, ProcessResult
from .platforms.registry import resolve_platform
from .shownotes import fetch_xiaoyuzhou_shownote
from .storage import save_result
from .subtitles import extract_subtitles, fetch_video_metadata
from .summarizer import refine_text, summarize_text
from .utils import cleanup_paths, ensure_directory

logger = logging.getLogger(__name__)


def _build_media_source(url: str, adapter: Any, metadata: dict[str, str | None] | None = None) -> MediaSource:
    normalized = adapter.normalize_url(url)
    metadata = metadata or {}
    return MediaSource(
        url=url,
        normalized_url=normalized,
        platform=adapter.name,
        title=metadata.get("title"),
        metadata={k: v for k, v in metadata.items() if v is not None},
    )


def _build_run_dir(base_temp_dir: Path, adapter_name: str) -> Path:
    run_id = uuid.uuid4().hex[:8]
    return ensure_directory(base_temp_dir / adapter_name / run_id)


def process_media(
    url: str,
    *,
    write_to_feishu: bool = True,
    cleanup: bool = True,
    skip_summarization: bool = False,
    persist_result: bool = True,
    save_markdown_file: bool = True,
    summarizer_client: Any | None = None,
    feishu_session: Any | None = None,
) -> ProcessResult:
    settings = ensure_runtime_dirs(get_settings())
    configure_logging(settings)
    adapter = resolve_platform(url)
    meta = fetch_video_metadata(url)
    source = _build_media_source(url, adapter, meta)
    run_dir = _build_run_dir(settings.temp_dir, adapter.name)
    temp_paths: list[Path] = [run_dir]

    notify_start(url, session=feishu_session)

    # Extract hot comments (non-blocking, YouTube/Bilibili/Xiaoyuzhou)
    hot_comments = None
    if source.platform in ("youtube", "bilibili", "xiaoyuzhou"):
        hot_comments = fetch_comments(source.normalized_url, platform=source.platform, timeout=settings.request_timeout)

    shownote = None
    if source.platform == "xiaoyuzhou":
        shownote = fetch_xiaoyuzhou_shownote(source.normalized_url, timeout=settings.request_timeout)

    try:
        subtitle_result = extract_subtitles(adapter, source.normalized_url, run_dir)
        if subtitle_result is not None:
            raw_text = subtitle_result.text
            transcript_source = "subtitles"
            artifacts = {"subtitle_path": str(subtitle_result.source_path)} if subtitle_result.source_path else {}
        else:
            transcript_result = extract_audio_and_transcribe(adapter, source.normalized_url, run_dir)
            raw_text = transcript_result.text
            transcript_source = "asr"
            artifacts = {"audio_path": str(transcript_result.audio_path)} if transcript_result.audio_path else {}

        cleaned = clean_transcript_text(raw_text)
        if transcript_source == "asr":
            logger.info("refining ASR transcript (纠错+分段)")
            cleaned = refine_text(cleaned, client=summarizer_client)
        segments = split_segments(cleaned)
        summary = summarize_text(source, "\n\n".join(segments), client=summarizer_client) if not skip_summarization else None
        feishu_result = publish_summary(summary, cleaned, description=source.metadata.get("description"), hot_comments=hot_comments, shownote=shownote, session=feishu_session) if write_to_feishu and summary else None
        if feishu_result and summary:
            notify_success(url, feishu_result.doc_token, summary.title, session=feishu_session)

        result = ProcessResult(
            source=source,
            transcript_source=transcript_source,
            transcript=cleaned,
            segments=segments,
            summary=summary,
            feishu=feishu_result,
            comments=hot_comments,
            shownote=shownote,
            artifacts=artifacts,
        )

        # 保存结果到本地
        if persist_result:
            try:
                save_result(result, settings.work_dir)
            except Exception as exc:
                logger.warning("failed to save result: %s", exc)

        # 保存 Markdown 到本地
        if save_markdown_file:
            try:
                md_path = save_markdown(result, settings.markdown_dir)
                logger.info("saved markdown: %s", md_path)
            except Exception as exc:
                logger.warning("failed to save markdown: %s", exc)

        logger.info("processed media url=%s source=%s", source.normalized_url, transcript_source)
        return result
    except Exception as exc:
        notify_failure(url, str(exc), session=feishu_session)
        raise
    finally:
        if cleanup:
            cleanup_paths(temp_paths)


def process_media_as_dict(**kwargs: Any) -> dict[str, Any]:
    return asdict(process_media(**kwargs))


def process_media_as_json(**kwargs: Any) -> str:
    return json.dumps(process_media_as_dict(**kwargs), ensure_ascii=False, indent=2)
