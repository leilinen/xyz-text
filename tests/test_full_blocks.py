#!/usr/bin/env python3
"""测试完整的 Feishu block 结构"""

import requests
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_tool.config import get_settings, require_feishu_credentials
from media_tool.feishu import get_tenant_access_token, create_document

# 测试不同类型的 block
def test_block_structure(name: str, blocks: list) -> bool:
    """测试给定的 block 结构是否能成功写入"""
    settings = get_settings()

    token = get_tenant_access_token()
    doc_token = create_document(f"测试: {name}", token)
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"children": blocks},
        timeout=30
    )

    print(f"\n{name}:")
    print(f"  状态码: {response.status_code}")

    if response.status_code == 200:
        payload = response.json()
        if payload.get("code") == 0:
            print(f"  ✅ 成功")
            return True
        else:
            print(f"  ❌ API 错误: {payload.get('msg')} (code: {payload.get('code')})")
            return False
    else:
        print(f"  ❌ HTTP 错误")
        return False

# 测试 1: 只有文本
test_block_structure("只有文本", [
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "这是普通文本"}}]}},
])

# 测试 2: Heading 1
test_block_structure("Heading 1", [
    {"block_type": 2, "heading1": {"elements": [{"text_run": {"content": "这是一级标题"}}]}},
])

# 测试 3: Heading 2
test_block_structure("Heading 2", [
    {"block_type": 3, "heading2": {"elements": [{"text_run": {"content": "这是二级标题"}}]}},
])

# 测试 4: 混合内容
test_block_structure("混合内容", [
    {"block_type": 2, "heading1": {"elements": [{"text_run": {"content": "标题"}}]}},
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "普通文本"}}]}},
])

# 测试 5: 原代码的 bullet 格式 (使用文本块加 "•")
test_block_structure("Bullet 列表", [
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "• 第一点"}}]}},
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "• 第二点"}}]}},
])

# 测试 6: 真正的 bullet list block
test_block_structure("真正的 Bullet Block", [
    {"block_type": 2, "bullet": {"elements": [{"text_run": {"content": "第一点"}}]}},
])

print("\n" + "="*50)
print("所有测试完成")
