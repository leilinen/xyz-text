#!/usr/bin/env python3
"""测试不同的 heading block 格式"""

import json
import requests
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_tool.core.config import get_settings
from media_tool.integrations.feishu import get_tenant_access_token, create_document

settings = get_settings()
if not settings.feishu_app_id or not settings.feishu_app_secret:
    pytest.skip("Feishu credentials are required for live API checks", allow_module_level=True)

def check_format(name: str, block: dict) -> bool:
    """测试单个 block 格式"""
    token = get_tenant_access_token()
    doc_token = create_document(f"测试:{name}", token)
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"children": [block]},
        timeout=30
    )

    success = response.status_code == 200 and response.json().get("code") == 0
    status = "✅" if success else "❌"
    print(f"{status} {name}")

    if not success:
        print(f"   响应: {response.text[:200]}")

    return success

print("测试不同的 Heading 格式:\n")

# 格式 1: 当前代码使用的格式
check_format("格式1: block_type=2 + heading1", {
    "block_type": 2,
    "heading1": {
        "elements": [{"text_run": {"content": "标题"}}]
    }
})

# 格式 2: block_type=1 + heading1
check_format("格式2: block_type=1 + heading1", {
    "block_type": 1,
    "heading1": {
        "elements": [{"text_run": {"content": "标题"}}]
    }
})

# 格式 3: 只用 text 字段，但设置样式
check_format("格式3: text + styled text_run", {
    "block_type": 2,
    "text": {
        "elements": [{
            "text_run": {
                "content": "标题",
                "text_element_style": {"bold": True}
            }
        }]
    }
})

# 格式 4: 尝试 paragraph
check_format("格式4: paragraph block", {
    "block_type": 1,
    "paragraph": {
        "elements": [{"text_run": {"content": "段落"}}]
    }
})

# 格式 5: 看看 block_type=1 是什么
check_format("格式5: block_type=1 only", {
    "block_type": 1
})

# 格式 6: 使用 index
check_format("格式6: with index field", {
    "block_type": 2,
    "heading1": {
        "elements": [{"text_run": {"content": "标题"}}],
        "index": 1
    }
})

# 格式 7: 尝试 style 字段
check_format("格式7: heading1 with style", {
    "block_type": 2,
    "heading1": {
        "elements": [{"text_run": {"content": "标题"}}],
        "style": {}
    }
})

print("\n完成!")
