"""本地持久化功能 - 保存和加载处理结果"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import ProcessResult

logger = logging.getLogger(__name__)


def generate_result_filename(platform: str, url: str, timestamp: str) -> str:
    """生成结果文件名"""
    # 使用时间戳的前 8 位 + 平台 + URL hash 的前 8 位
    url_hash = hash(url) % 10**8
    return f"{timestamp}_{platform}_{url_hash:08x}.json"


def save_result(result: ProcessResult, output_dir: Path) -> Path:
    """
    将处理结果保存为 JSON 文件

    Args:
        result: 处理结果
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    output_dir = output_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = generate_result_filename(result.source.platform, result.source.url, timestamp)
    filepath = output_dir / filename

    # 将 dataclass 转换为字典，处理 Path 类型和 None 值
    data = asdict(result)
    # 清理 None 值和特殊类型
    data = json.loads(json.dumps(data, default=str))

    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("saved result to: %s", filepath)
    return filepath


def load_result(filepath: Path) -> dict:
    """
    从 JSON 文件加载处理结果

    Args:
        filepath: JSON 文件路径

    Returns:
        包含处理结果的字典
    """
    if not filepath.exists():
        raise FileNotFoundError(f"结果文件不存在: {filepath}")

    data = json.loads(filepath.read_text(encoding="utf-8"))
    logger.info("loaded result from: %s", filepath)
    return data


def retry_feishu_upload(
    filepath: Path,
    summary_data: dict,
    transcript: str,
    session: object | None = None,
    shownote_data: dict | None = None,
) -> tuple:
    """
    从本地保存的结果重新上传到 Feishu

    Args:
        filepath: JSON 文件路径
        summary_data: 总结数据字典
        transcript: 转录文本
        session: 可选的 requests.Session

    Returns:
        (summary_result, feishu_result) 元组
    """
    from .feishu import publish_summary
    from .models import ShownoteContent, SummaryResult
    from .summarizer import _coerce_entities

    # 重建 SummaryResult 对象
    summary = SummaryResult(
        title=summary_data.get("title", ""),
        summary=summary_data.get("summary", ""),
        one_line_summary=summary_data.get("one_line_summary", ""),
        topics=summary_data.get("topics", []),
        key_points=summary_data.get("key_points", []),
        quotes=summary_data.get("quotes", []),
        entities=_coerce_entities(summary_data),
        raw_response=summary_data.get("raw_response"),
    )

    shownote = None
    if shownote_data:
        shownote = ShownoteContent(
            text=shownote_data.get("text", ""),
            images=shownote_data.get("images", []),
        )

    # 重新上传
    feishu_result = publish_summary(summary, transcript, session=session, shownote=shownote)

    return summary, feishu_result
