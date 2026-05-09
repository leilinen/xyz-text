#!/usr/bin/env python3
"""测试 Feishu block 结构"""

import requests
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_tool.config import get_settings, require_feishu_credentials
from media_tool.feishu import get_tenant_access_token, create_document

# 根据 Feishu 官方文档，正确的 block 结构
def correct_text_block(text: str) -> dict:
    return {
        "block_type": 2,  # 2 代表文本块
        "text": {
            "elements": [
                {
                    "text_run": {
                        "content": text
                    }
                }
            ]
        }
    }

def correct_heading_block(text: str, level: int = 1) -> dict:
    # heading1: block_type=2, heading2: block_type=3
    block_type = 2 if level == 1 else 3
    heading_key = "heading1" if level == 1 else "heading2"
    return {
        "block_type": block_type,
        heading_key: {
            "elements": [
                {
                    "text_run": {
                        "content": text
                    }
                }
            ]
        }
    }

# 测试获取 token 和创建文档
settings = get_settings()
app_id, app_secret = require_feishu_credentials(settings)

print("测试 1: 获取 tenant_access_token")
token = get_tenant_access_token()
print(f"✅ Token 获取成功: {token[:20]}...")

print("\n测试 2: 创建文档")
doc_token = create_document("测试文档", token)
print(f"✅ 文档创建成功: {doc_token}")

print("\n测试 3: 写入简单的文本块")
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"

# 先测试一个简单的文本块
simple_blocks = [
    correct_text_block("这是第一行文本")
]

response = requests.post(
    url,
    headers={"Authorization": f"Bearer {token}"},
    json={"children": simple_blocks},
    timeout=30
)

print(f"响应状态码: {response.status_code}")
print(f"响应内容: {response.text}")

if response.status_code == 200:
    payload = response.json()
    if payload.get("code") == 0:
        print("✅ 简单文本块写入成功")
    else:
        print(f"❌ API 返回错误: {payload}")
else:
    print(f"❌ HTTP 请求失败")
