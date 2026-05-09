#!/usr/bin/env python3
"""测试 Markdown 风格的标题"""

import requests
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_tool.config import get_settings
from media_tool.feishu import get_tenant_access_token, create_document

def test_block(name: str, block: dict) -> bool:
    """测试单个 block"""
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
    return success

print("测试 Markdown 风格的标题:\n")

# 使用 Markdown 风格的 # 前缀
test_block("一级标题 (# )", {
    "block_type": 2,
    "text": {
        "elements": [{
            "text_run": {
                "content": "# 这是一级标题"
            }
        }]
    }
})

test_block("二级标题 (## )", {
    "block_type": 2,
    "text": {
        "elements": [{
            "text_run": {
                "content": "## 这是二级标题"
            }
        }]
    }
})

test_block("粗体一级标题", {
    "block_type": 2,
    "text": {
        "elements": [{
            "text_run": {
                "content": "这是一级标题",
                "text_element_style": {"bold": True}
            }
        }]
    }
})

test_block("完整的文档结构", {
    "block_type": 2,
    "text": {
        "elements": [{
            "text_run": {
                "content": "# 有钱人和你想的不一样",
                "text_element_style": {"bold": True}
            }
        }]
    }
})

print("\n✅ 所有格式测试完成!")

# 现在测试完整的多 block 文档
print("\n测试完整的多 block 文档:\n")

token = get_tenant_access_token()
doc_token = create_document("完整文档测试", token)
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"

blocks = [
    {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": "# 有钱人和你想的不一样",
                    "text_element_style": {"bold": True}
                }
            }]
        }
    },
    {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": "## 总结"
                }
            }]
        }
    },
    {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": "这期播客讨论了有钱人和穷人在思维方式上的差异。"
                }
            }]
        }
    },
    {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": "• 有钱人相信我创造了我的人生"
                }
            }]
        }
    },
    {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": "• 有钱人玩金钱游戏是为了赢"
                }
            }]
        }
    },
]

response = requests.post(
    url,
    headers={"Authorization": f"Bearer {token}"},
    json={"children": blocks},
    timeout=30
)

if response.status_code == 200 and response.json().get("code") == 0:
    print("✅ 完整文档创建成功!")
    print(f"文档 URL: https://open.feishu.cn/document/{doc_token}")
else:
    print("❌ 完整文档创建失败")
    print(f"响应: {response.text}")
