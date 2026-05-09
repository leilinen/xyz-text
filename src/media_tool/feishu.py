from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .cleaner import split_paragraphs
from .config import get_settings, require_feishu_credentials
from .models import ENTITY_TYPE_LABELS, FeishuDocResult, HotCommentsResult, ShownoteContent, SummaryResult
from .utils import FeishuAPIError

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_DOC_CREATE_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
_DOC_BLOCK_URL_TEMPLATE = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{block_id}/children"
_SHARE_URL_TEMPLATE = "https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_token}/members?type=docx"
_TRANSFER_OWNER_URL_TEMPLATE = "https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_token}/members/transfer_owner?type=docx"
_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"


def _parse_feishu_response(response: requests.Response, action: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise FeishuAPIError(f"failed to {action}: invalid JSON response") from exc
    if response.status_code != 200 or payload.get("code") != 0:
        raise FeishuAPIError(f"failed to {action}: {payload}")
    return payload


def get_tenant_access_token(session: requests.Session | None = None) -> str:
    settings = get_settings()
    app_id, app_secret = require_feishu_credentials(settings)
    session = session or requests.Session()
    response = session.post(
        _TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=settings.request_timeout,
    )
    payload = _parse_feishu_response(response, "get tenant access token")
    return str(payload["tenant_access_token"])


def create_document(title: str, token: str, session: requests.Session | None = None) -> str:
    settings = get_settings()
    session = session or requests.Session()
    response = session.post(
        _DOC_CREATE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title},
        timeout=settings.request_timeout,
    )
    payload = _parse_feishu_response(response, "create document")
    return str(payload["data"]["document"]["document_id"])


def _text_block(text: str) -> dict[str, Any]:
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": text}}]}}


def _heading_block(text: str, level: int = 1) -> dict[str, Any]:
    block_type = level + 2  # heading1=3, heading2=4, heading3=5
    return {
        "block_type": block_type,
        f"heading{level}": {
            "elements": [
                {"text_run": {"content": text, "text_element_style": {}}}
            ]
        },
    }


def _bullet_blocks(items: list[str]) -> list[dict[str, Any]]:
    return [_text_block(f"• {item}") for item in items if item]


def _build_blocks(
    summary: SummaryResult,
    transcript: str,
    description: str | None = None,
    hot_comments: HotCommentsResult | None = None,
    shownote: ShownoteContent | None = None,
) -> list[dict[str, Any]]:
    content = [
        _heading_block(summary.title, level=1),
    ]
    if summary.one_line_summary:
        content.append(_text_block(summary.one_line_summary))
    if description:
        content.append(_heading_block("节目介绍", level=2))
        for paragraph in split_paragraphs(description):
            content.append(_text_block(paragraph))
    if shownote and (shownote.text or shownote.images):
        content.append(_heading_block("Shownote", level=2))
        if shownote.text:
            for paragraph in split_paragraphs(shownote.text):
                content.append(_text_block(paragraph))
        for image_url in shownote.images:
            content.append(_text_block(f"图片: {image_url}"))
    if summary.entities:
        content.append(_heading_block("实体", level=2))
        for entity in summary.entities:
            type_label = ENTITY_TYPE_LABELS.get(entity.type, entity.type)
            content.append(_text_block(f"• {entity.name}（{type_label}）{entity.context}"))
    content.extend([
        _heading_block("总结", level=2),
        _text_block(summary.summary),
    ])
    content.extend(_bullet_blocks(summary.key_points))
    if summary.quotes:
        content.append(_heading_block("引用", level=2))
        content.extend(_bullet_blocks(summary.quotes))
    if hot_comments and hot_comments.comments:
        content.append(_heading_block("热门评论", level=2))
        for c in hot_comments.comments:
            label = ""
            if c.is_pinned:
                label = "[置顶] "
            elif c.is_creator_favorited:
                label = "[❤️] "
            content.append(_text_block(f"{label}{c.author}：{c.text}"))
            content.append(_text_block(f"👍 {c.like_count}"))
    content.append(_heading_block("转录全文", level=2))
    for paragraph in split_paragraphs(transcript):
        content.append(_text_block(paragraph))
    return content


_FEISHU_MAX_CHILDREN = 50


def _append_blocks(doc_token: str, parent_block_id: str, children: list[dict[str, Any]], token: str, session: requests.Session, timeout: int) -> None:
    url = _DOC_BLOCK_URL_TEMPLATE.format(doc_token=doc_token, block_id=parent_block_id)
    response = session.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"children": children},
        timeout=timeout,
    )
    _parse_feishu_response(response, "write document content")


def write_document_content(
    doc_token: str,
    summary: SummaryResult,
    transcript: str,
    token: str,
    session: requests.Session | None = None,
    description: str | None = None,
    hot_comments: HotCommentsResult | None = None,
    shownote: ShownoteContent | None = None,
) -> None:
    settings = get_settings()
    session = session or requests.Session()
    blocks = _build_blocks(summary, transcript, description=description, hot_comments=hot_comments, shownote=shownote)

    # Feishu API limits children to 50 per request; batch if needed
    for i in range(0, len(blocks), _FEISHU_MAX_CHILDREN):
        batch = blocks[i : i + _FEISHU_MAX_CHILDREN]
        _append_blocks(doc_token, doc_token, batch, token, session, settings.request_timeout)
    logger.info("wrote Feishu document content: %s (%d blocks)", doc_token, len(blocks))


def share_document(doc_token: str, user_id: str, token: str, session: requests.Session | None = None) -> None:
    settings = get_settings()
    session = session or requests.Session()
    url = _SHARE_URL_TEMPLATE.format(doc_token=doc_token)
    response = session.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "member_type": "openid",
            "member_id": user_id,
            "perm": "full_access",
            "type": "user",
        },
        timeout=settings.request_timeout,
    )
    _parse_feishu_response(response, "share document")
    logger.info("shared Feishu document %s with user %s", doc_token, user_id)


def transfer_ownership(doc_token: str, user_id: str, token: str, session: requests.Session | None = None) -> None:
    settings = get_settings()
    session = session or requests.Session()
    url = _TRANSFER_OWNER_URL_TEMPLATE.format(doc_token=doc_token)
    response = session.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "member_type": "openid",
            "member_id": user_id,
        },
        timeout=settings.request_timeout,
    )
    _parse_feishu_response(response, "transfer ownership")
    logger.info("transferred ownership of Feishu document %s to user %s", doc_token, user_id)


def build_doc_url(doc_token: str) -> str:
    # 注意：这个 URL 只是一个标识，实际访问需要使用你的 Feishu 域名
    # 正确的格式是: https://{your_domain}.feishu.cn/docx/{doc_token}
    # 建议在 Feishu 中搜索文档标题，或查看"最近使用"
    return f"feishu:docx:{doc_token}"


def send_message(receive_id: str, msg_type: str, content: str, token: str, session: requests.Session | None = None) -> dict[str, Any]:
    settings = get_settings()
    session = session or requests.Session()
    response = session.post(
        _MESSAGE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": receive_id, "msg_type": msg_type, "content": content},
        timeout=settings.request_timeout,
    )
    payload = _parse_feishu_response(response, "send message")
    logger.info("sent Feishu message to %s (type=%s)", receive_id, msg_type)
    return payload


def _notify(text: str, session: requests.Session | None = None) -> None:
    settings = get_settings()
    if not settings.feishu_share_user_id:
        return
    try:
        token = get_tenant_access_token(session=session)
        send_message(
            settings.feishu_share_user_id,
            "text",
            json.dumps({"text": text}, ensure_ascii=False),
            token,
            session=session,
        )
    except Exception:
        logger.warning("failed to send Feishu notification", exc_info=True)


def notify_start(url: str, session: requests.Session | None = None) -> None:
    _notify(f"开始处理媒体\nURL: {url}", session=session)


def notify_success(url: str, doc_token: str, title: str, session: requests.Session | None = None) -> None:
    _notify(
        f"处理完成\n标题: {title}\nURL: {url}\n文档: https://feishu.cn/docx/{doc_token}",
        session=session,
    )


def notify_failure(url: str, error: str, session: requests.Session | None = None) -> None:
    _notify(f"处理失败\nURL: {url}\n错误: {error}", session=session)


def publish_summary(
    summary: SummaryResult,
    transcript: str,
    session: requests.Session | None = None,
    description: str | None = None,
    hot_comments: HotCommentsResult | None = None,
    shownote: ShownoteContent | None = None,
) -> FeishuDocResult:
    token = get_tenant_access_token(session=session)
    doc_token = create_document(summary.title, token, session=session)
    write_document_content(doc_token, summary, transcript, token, session=session, description=description, hot_comments=hot_comments, shownote=shownote)

    settings = get_settings()
    if settings.feishu_share_user_id:
        share_document(doc_token, settings.feishu_share_user_id, token, session=session)
        transfer_ownership(doc_token, settings.feishu_share_user_id, token, session=session)

    logger.info("=" * 60)
    logger.info("Feishu document created!")
    logger.info("   Title: %s", summary.title)
    logger.info("   Doc ID: %s", doc_token)
    if settings.feishu_share_user_id:
        logger.info("   Shared to user: %s", settings.feishu_share_user_id)
    logger.info("   URL: https://feishu.cn/docx/%s", doc_token)
    logger.info("=" * 60)

    return FeishuDocResult(doc_token=doc_token, url=build_doc_url(doc_token))
