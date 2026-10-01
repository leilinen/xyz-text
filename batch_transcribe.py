#!/usr/bin/env python3
"""Batch transcribe downloaded videos and upload to Feishu."""

import json
import logging
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from media_tool.core.config import get_settings, configure_logging, ensure_runtime_dirs
from media_tool.integrations.feishu import (
    get_tenant_access_token,
    create_document,
    _text_block,
    _heading_block,
    _append_blocks,
)
from media_tool.text.cleaner import split_paragraphs

logger = logging.getLogger(__name__)

VIDEO_DIR = Path.home() / "Downloads" / "太妃Tefi价格行为学核心课"
TRANSCRIPT_DIR = Path.home() / "Downloads" / "太妃Tefi价格行为学核心课_transcripts"


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """Extract audio from video using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-q:a", "4",
        "-y", str(output_path),
    ]
    logger.info("extracting audio: %s", video_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {video_path}: {result.stderr[:300]}")
    return output_path


def transcribe_with_sensevoice(audio_path: Path) -> str:
    """Transcribe audio file using SenseVoice."""
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    settings = get_settings()
    model_path = settings.sensevoice_model_path
    if model_path:
        p = Path(model_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent / p
        model_path = str(p)

    logger.info("loading SenseVoice model (device=%s)", settings.sensevoice_device)
    model = AutoModel(
        model=model_path or "iic/SenseVoiceSmall",
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device=settings.sensevoice_device,
    )

    res = model.generate(
        input=str(audio_path),
        language=settings.sensevoice_language,
        use_itn=True,
        batch_size_s=60,
        merge_vad=True,
        merge_length_s=15,
    )

    text = rich_transcription_postprocess(res[0]["text"])
    return text


def upload_to_feishu(transcripts: list[tuple[str, str]]):
    """Create a Feishu doc with all transcripts."""
    settings = get_settings()
    session = __import__("requests").Session()

    token = get_tenant_access_token(session=session)
    doc_token = create_document("太妃Tefi价格行为学核心课 - 转录全文", token, session=session)

    blocks = [_heading_block("太妃Tefi价格行为学核心课", level=1)]

    for title, transcript in transcripts:
        blocks.append(_heading_block(title, level=2))
        for paragraph in split_paragraphs(transcript):
            blocks.append(_text_block(paragraph))

    # Feishu API limits to 50 blocks per request
    for i in range(0, len(blocks), 50):
        batch = blocks[i:i + 50]
        _append_blocks(doc_token, doc_token, batch, token, session, settings.request_timeout)

    print(f"\n{'='*60}")
    print(f"Feishu document created!")
    print(f"URL: https://feishu.cn/docx/{doc_token}")
    print(f"{'='*60}")

    # Share with user
    if settings.feishu_share_user_id:
        from media_tool.integrations.feishu import share_document, transfer_ownership
        share_document(doc_token, settings.feishu_share_user_id, token, session=session)
        transfer_ownership(doc_token, settings.feishu_share_user_id, token, session=session)
        print(f"Shared to user and transferred ownership.")


def main():
    settings = get_settings()
    configure_logging(settings)
    ensure_runtime_dirs(settings)

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all video files, sorted by name
    videos = sorted(VIDEO_DIR.glob("*.mp4"))
    if not videos:
        print("No MP4 files found in", VIDEO_DIR)
        sys.exit(1)

    print(f"Found {len(videos)} videos to transcribe")

    transcripts: list[tuple[str, str]] = []

    for i, video in enumerate(videos, 1):
        # Extract a short title from filename
        # Format: "01 【搬】... p01 L01 重新认识你所参与的这场游戏 A.mp4"
        name = video.stem
        # Extract lesson info after "pXX"
        parts = name.split(" ")
        # Find the part starting with "p" followed by digits
        title = name
        for j, part in enumerate(parts):
            if part.startswith("p") and part[1:].isdigit():
                title = " ".join(parts[j:])  # "p01 L01 重新认识你所参与的这场游戏 A"
                break

        transcript_file = TRANSCRIPT_DIR / f"{i:02d}.txt"

        if transcript_file.exists():
            logger.info("[%d/%d] transcript exists, loading: %s", i, len(videos), title)
            text = transcript_file.read_text(encoding="utf-8")
        else:
            logger.info("[%d/%d] processing: %s", i, len(videos), title)
            audio_path = TRANSCRIPT_DIR / f"{i:02d}.mp3"

            # Extract audio
            extract_audio(video, audio_path)

            # Transcribe
            text = transcribe_with_sensevoice(audio_path)

            # Save transcript
            transcript_file.write_text(text, encoding="utf-8")
            logger.info("saved transcript (%d chars): %s", len(text), transcript_file)

            # Cleanup audio to save disk
            audio_path.unlink(missing_ok=True)

            print(f"[{i}/{len(videos)}] done: {title} ({len(text)} chars)")

        transcripts.append((title, text))

    # Upload to Feishu
    logger.info("uploading %d transcripts to Feishu", len(transcripts))
    upload_to_feishu(transcripts)


if __name__ == "__main__":
    main()
