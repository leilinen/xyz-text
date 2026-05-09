from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_tool.pipeline import process_media
from media_tool.storage import load_result, retry_feishu_upload
from media_tool.utils import MediaToolError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe media links and generate summaries.")
    parser.add_argument("url", nargs="?", help="Media URL to process (not required with --retry)")
    parser.add_argument("--retry", type=Path, help="Retry Feishu upload from a saved JSON file")
    parser.add_argument("--no-feishu", action="store_true", help="Skip Feishu document publishing")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep temporary files")
    parser.add_argument("--no-summary", action="store_true", help="Skip AI summarization (requires no API key)")
    parser.add_argument("--output", "-o", type=Path, help="Save transcript to file")
    return parser.parse_args()


def _build_error_payload(exc: Exception) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "error": str(exc) or exc.__class__.__name__,
        "error_type": exc.__class__.__name__,
    }
    if isinstance(exc, MediaToolError):
        payload["error_category"] = "media_tool"
    else:
        payload["error_category"] = "unexpected"
    return payload


def main() -> int:
    args = parse_args()

    # 模式 1: 从 JSON 文件重试 Feishu 上传
    if args.retry:
        if not args.retry.exists():
            print(json.dumps({"ok": False, "error": f"文件不存在: {args.retry}"}, ensure_ascii=False))
            return 1

        try:
            data = load_result(args.retry)

            # 检查是否有 summary 数据
            if data.get("summary") is None:
                print(json.dumps({"ok": False, "error": "保存的结果中没有 summary 数据，无法重试上传"}, ensure_ascii=False))
                return 1

            # 重新上传到 Feishu
            summary, feishu_result = retry_feishu_upload(
                args.retry,
                data["summary"],
                data["transcript"],
                shownote_data=data.get("shownote"),
            )

            # 更新数据
            data["feishu"] = asdict(feishu_result)

            print(json.dumps({"ok": True, "result": data}, ensure_ascii=False, indent=2))
            print("\n" + "=" * 60, file=sys.stderr)
            print("✅ 重新上传成功!", file=sys.stderr)
            print(f"   文档 ID: {feishu_result.doc_token}", file=sys.stderr)
            print("   请在 Feishu 中搜索标题，或查看'最近使用'", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            return 0

        except Exception as exc:
            print(json.dumps(_build_error_payload(exc), ensure_ascii=False))
            return 1

    # 模式 2: 正常处理流程
    if not args.url:
        print(json.dumps({"ok": False, "error": "请提供 URL 或使用 --retry 参数"}, ensure_ascii=False))
        return 1

    try:
        result = process_media(
            args.url,
            write_to_feishu=not args.no_feishu,
            cleanup=not args.no_cleanup,
            skip_summarization=args.no_summary,
            save_markdown_file=True,
        )
    except Exception as exc:
        print(json.dumps(_build_error_payload(exc), ensure_ascii=False))
        return 1

    # Save transcript to file if --output is specified
    if args.output:
        args.output.write_text(result.transcript, encoding="utf-8")
        print(f"Transcript saved to: {args.output}", file=sys.stderr)

    print(json.dumps({"ok": True, "result": asdict(result)}, ensure_ascii=False, indent=2))

    # 如果成功上传到 Feishu，显示友好的提示
    if result.feishu:
        print("\n" + "=" * 60, file=sys.stderr)
        print("✅ 文档已上传到 Feishu!", file=sys.stderr)
        print(f"   文档标题: {result.summary.title if result.summary else 'N/A'}", file=sys.stderr)
        print(f"   文档 ID: {result.feishu.doc_token}", file=sys.stderr)
        print("   请在 Feishu 中搜索标题，或查看'最近使用'", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
