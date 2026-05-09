from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import get_settings
from .models import TranscriptResult
from .utils import ASRError, ExternalCommandError

logger = logging.getLogger(__name__)

_AUDIO_SUFFIX_PRIORITY = (".mp3", ".m4a", ".wav", ".mp4", ".webm", ".opus", ".ogg", ".aac", ".flac")


def download_audio(request_args: list[str], url: str) -> None:
    command = ["yt-dlp", *request_args, url]
    logger.info("downloading audio: %s", " ".join(command))
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info("yt-dlp stdout: %s", result.stdout[:500] if result.stdout else "(empty)")
    except subprocess.CalledProcessError as exc:
        logger.error("yt-dlp failed (rc=%d): stderr=%s", exc.returncode, exc.stderr[:500] if exc.stderr else "(empty)")
        raise ExternalCommandError(exc.stderr.strip() or exc.stdout.strip() or "yt-dlp audio download failed") from exc


def transcribe_audio_with_sensevoice(audio_path: Path) -> TranscriptResult:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    settings = get_settings()
    model_path = settings.sensevoice_model_path
    if model_path:
        # Resolve relative paths from project root
        p = Path(model_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[2] / p
        model_path = str(p)

    logger.info("loading SenseVoice model from: %s (device=%s)", model_path or "iic/SenseVoiceSmall", settings.sensevoice_device)
    logger.info("audio file: %s (size: %s bytes)", audio_path, audio_path.stat().st_size if audio_path.exists() else "N/A")

    try:
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
    except Exception as exc:
        raise ASRError(f"sensevoice transcription failed: {exc}") from exc

    text = rich_transcription_postprocess(res[0]["text"])
    logger.info("sensevoice transcription done (%d chars)", len(text))
    return TranscriptResult(text=text, segments=[], audio_path=audio_path)


def transcribe_audio(audio_path: Path) -> TranscriptResult:
    return transcribe_audio_with_sensevoice(audio_path)


def _audio_sort_key(path: Path) -> tuple[int, str]:
    suffix = path.suffix.lower()
    try:
        suffix_rank = _AUDIO_SUFFIX_PRIORITY.index(suffix)
    except ValueError:
        suffix_rank = len(_AUDIO_SUFFIX_PRIORITY)
    return (suffix_rank, path.name.lower())


def choose_audio_file(paths: list[Path]) -> Path | None:
    candidates = [path for path in paths if path.is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=_audio_sort_key)[0]


def extract_audio_and_transcribe(
    adapter: object,
    url: str,
    work_dir: Path,
) -> TranscriptResult:
    output_template = str(work_dir / "%(title)s.%(ext)s")
    request = adapter.build_audio_request(url, output_template)
    download_audio(request.args, request.url)
    audio_files = [path for path in work_dir.iterdir() if path.suffix.lower() in _AUDIO_SUFFIX_PRIORITY]
    selected_audio = choose_audio_file(audio_files)
    if selected_audio is None:
        supported = ", ".join(suffix.lstrip(".") for suffix in _AUDIO_SUFFIX_PRIORITY)
        raise ExternalCommandError(f"audio download completed but no supported audio file was produced ({supported})")
    return transcribe_audio(selected_audio)
