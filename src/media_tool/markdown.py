"""将处理结果保存为本地 Markdown 文件"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import yaml

from .cleaner import split_paragraphs
from .models import ENTITY_TYPE_LABELS, ProcessResult

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str) -> str:
    """将标题转为安全的文件名（去除特殊字符，截断过长标题）"""
    name = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    name = re.sub(r'\s+', ' ', name)
    return name[:80] if name else "untitled"


def build_markdown(result: ProcessResult) -> str:
    """将 ProcessResult 转换为 Markdown 文本"""
    parts: list[str] = []

    summary = result.summary
    source = result.source
    description = source.metadata.get("description")

    title = summary.title if summary else (source.title or "untitled")

    # YAML frontmatter
    frontmatter: dict = {
        "platform": source.platform,
        "url": source.url,
        "date": date.today().isoformat(),
    }
    if summary:
        if summary.topics:
            frontmatter["topics"] = summary.topics
        if summary.entities:
            frontmatter["entities"] = [e.name for e in summary.entities]
    parts.append("---")
    parts.append(yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip())
    parts.append("---\n")

    # Title
    parts.append(f"# {title}\n")

    # One-line summary
    if summary and summary.one_line_summary:
        parts.append(f"> {summary.one_line_summary}\n")

    # Description
    if description:
        parts.append("## 节目介绍\n")
        for paragraph in split_paragraphs(description):
            parts.append(f"{paragraph}\n")

    # Shownote
    if result.shownote and (result.shownote.text or result.shownote.images):
        parts.append("## Shownote\n")
        if result.shownote.text:
            for paragraph in split_paragraphs(result.shownote.text):
                parts.append(f"{paragraph}\n")
        for image_url in result.shownote.images:
            parts.append(f"![]({image_url})\n")

    # Entities
    if summary and summary.entities:
        parts.append("## 实体\n")
        for entity in summary.entities:
            type_label = ENTITY_TYPE_LABELS.get(entity.type, entity.type)
            parts.append(f"- **{entity.name}**（{type_label}）{entity.context}")
        parts.append("")

    # Summary
    if summary:
        parts.append("## 总结\n")
        parts.append(f"{summary.summary}\n")

        if summary.key_points:
            parts.append("### 要点\n")
            for point in summary.key_points:
                parts.append(f"- {point}")
            parts.append("")

        if summary.quotes:
            parts.append("### 引用\n")
            for quote in summary.quotes:
                parts.append(f"> {quote}")
            parts.append("")

    # Hot comments
    if result.comments and result.comments.comments:
        parts.append("## 热门评论\n")
        for c in result.comments.comments:
            label = ""
            if c.is_pinned:
                label = "[置顶] "
            elif c.is_creator_favorited:
                label = "[❤️] "
            parts.append(f"- {label}{c.author}：{c.text} (👍 {c.like_count})")
        parts.append("")

    # Transcript
    parts.append("## 转录全文\n")
    for paragraph in split_paragraphs(result.transcript):
        parts.append(f"{paragraph}\n")

    return "\n".join(parts)


def save_markdown(result: ProcessResult, base_dir: Path) -> Path:
    """
    将处理结果保存为 Markdown 文件

    Args:
        result: 处理结果
        base_dir: 基础输出目录

    Returns:
        保存的文件路径
    """
    today = date.today().isoformat()
    date_dir = base_dir / today
    date_dir.mkdir(parents=True, exist_ok=True)

    title = result.summary.title if result.summary else (result.source.title or None)
    if title:
        filename = f"{_sanitize_filename(title)}.md"
    else:
        from .storage import generate_result_filename
        timestamp = today.replace("-", "")
        filename = generate_result_filename(result.source.platform, result.source.url, timestamp).replace(".json", ".md")

    filepath = date_dir / filename

    # Avoid overwriting: append suffix if file exists
    if filepath.exists():
        stem = filepath.stem
        suffix = filepath.suffix
        counter = 1
        while filepath.exists():
            filepath = date_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    content = build_markdown(result)
    filepath.write_text(content, encoding="utf-8")
    logger.info("saved markdown to: %s", filepath)
    return filepath
