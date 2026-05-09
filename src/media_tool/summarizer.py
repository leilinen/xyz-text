from __future__ import annotations

import json
import logging
from typing import Any

from .config import get_settings
from .llm import LLMClient, create_llm_client
from .models import Entity, MediaSource, SummaryResult
from .utils import SummarizationError, safe_json_loads

_REFINE_CHUNK_SIZE = 8000

logger = logging.getLogger(__name__)


_REFINE_PROMPT = """你是一个中文语音转录文本的校对专家。请对以下ASR转录文本进行两步处理：

1. **纠错**：修正明显的同音错字、漏字、多字（如"积德利益"→"既得利益"、"股神不死"→"谷神不死"、"实磊"→"石磊"），使语句通顺。不要改变原意，不要增删内容，不要润色文风。

2. **分段**：按话题和逻辑段落分段，每段用空行分隔。

直接输出纠错和分段后的纯文本，不要加任何标题、编号或解释。"""

_PROMPT = """你是一个媒体内容分析助手。请分析输入的媒体内容文本。

【重要规则】你必须且只能输出一个合法的 JSON 对象。禁止输出任何其他内容：不要 Markdown 格式、不要解释说明、不要代码块包裹。

必须严格按照以下 JSON 格式输出：
{"title": "简短标题", "one_line_summary": "一句话摘要（中文，30字以内）", "summary": "200-500字的总结", "topics": ["主题1", "主题2"], "key_points": ["要点1", "要点2"], "quotes": ["金句1"], "entities": [{"name": "实体名", "type": "person|organization|book", "context": "提及上下文（简短）"}]}

所有字段都必须存在。title 为字符串，one_line_summary 为30字以内的一句话摘要，summary 为字符串，topics/key_points/quotes 为字符串数组。entities 为数组，列出提到的具体人物、组织、公司、书籍名称，数组可以为空。"""


def _build_messages(source: MediaSource, text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "url": source.normalized_url,
                    "platform": source.platform,
                    "title": source.title,
                    "text": text,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _coerce_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key) or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_entities(payload: dict[str, Any]) -> list[Entity]:
    raw = payload.get("entities") or []
    if not isinstance(raw, list):
        return []
    entities: list[Entity] = []
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                entities.append(Entity(
                    name=name,
                    type=str(item.get("type", "person")).strip(),
                    context=str(item.get("context", "")).strip(),
                ))
    return entities


def summarize_text(source: MediaSource, text: str, client: LLMClient | None = None) -> SummaryResult:
    settings = get_settings()
    clipped = text[: settings.summary_max_chars]
    if client is None:
        client = create_llm_client(settings)
    try:
        content = client.complete(_build_messages(source, clipped), temperature=0.3)
    except Exception as exc:
        raise SummarizationError(f"failed to summarize transcript: {exc}") from exc

    payload = safe_json_loads(content)
    title = source.title or str(payload.get("title") or "").strip() or f"{source.platform} media summary"
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise SummarizationError("model output missing summary field")
    one_line_summary = str(payload.get("one_line_summary") or "").strip()
    result = SummaryResult(
        title=title,
        summary=summary,
        one_line_summary=one_line_summary,
        topics=_coerce_list(payload, "topics"),
        key_points=_coerce_list(payload, "key_points"),
        quotes=_coerce_list(payload, "quotes"),
        entities=_coerce_entities(payload),
        raw_response=content,
    )
    logger.info("generated summary for %s", source.normalized_url)
    return result


def _split_refine_batches(text: str, max_chars: int = _REFINE_CHUNK_SIZE) -> list[str]:
    """Split text into batches at sentence boundaries for refine, each <= max_chars."""
    import re
    sentences = re.split(r"(?<=[。！？!?\.])", text.replace("\n", " "))
    sentences = [s.strip() for s in sentences if s.strip()]
    batches: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 2 > max_chars:
            batches.append(current)
            current = sentence
        else:
            current = (current + " " + sentence).strip() if current else sentence
    if current:
        batches.append(current)
    return batches


def _refine_batch(client: LLMClient, batch: str) -> str:
    """Refine a single batch via LLM (纠错+分段)."""
    return client.complete(
        messages=[
            {"role": "system", "content": _REFINE_PROMPT},
            {"role": "user", "content": batch},
        ],
        temperature=0.1,
    ).strip()


def refine_text(text: str, client: LLMClient | None = None) -> str:
    """Use LLM to correct ASR errors and add paragraph breaks.

    Replaces the old punctuate_text step. Handles homophones, proper nouns,
    missing/extra characters, and paragraph segmentation.
    """
    settings = get_settings()
    if client is None:
        client = create_llm_client(settings)

    batches = _split_refine_batches(text)
    logger.info("refining text in %d batch(es) (%d chars total)", len(batches), len(text))

    results: list[str] = []
    for i, batch in enumerate(batches):
        try:
            result = _refine_batch(client, batch)
            results.append(result)
            logger.info("batch %d/%d done (%d -> %d chars)", i + 1, len(batches), len(batch), len(result))
        except Exception as exc:
            raise SummarizationError(f"failed to refine batch {i + 1}/{len(batches)}: {exc}") from exc

    combined = "\n\n".join(results)
    logger.info("refined total: %d -> %d chars", len(text), len(combined))
    return combined
