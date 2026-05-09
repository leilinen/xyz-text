from __future__ import annotations

import os

import pytest
from pathlib import Path

from src.media_tool.config import get_settings
from src.media_tool.feishu import build_doc_url, create_document, get_tenant_access_token, publish_summary, write_document_content
from src.media_tool.models import ShownoteContent, SummaryResult
from src.media_tool.utils import FeishuAPIError


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"feishu_app_id":"app-id","feishu_app_secret":"app-secret"}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)


def test_get_tenant_access_token_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"feishu_app_id":"app-id","feishu_app_secret":"app-secret"}', encoding="utf-8")
    test_settings = get_settings(config_path)
    monkeypatch.setattr("src.media_tool.feishu.get_settings", lambda: test_settings)

    session = FakeSession([FakeResponse(200, {"code": 0, "tenant_access_token": "token-1"})])
    assert get_tenant_access_token(session=session) == "token-1"


def test_create_document_failure() -> None:
    session = FakeSession([FakeResponse(400, {"code": 999})])
    with pytest.raises(FeishuAPIError):
        create_document("Title", "token", session=session)


def test_write_document_content_success() -> None:
    session = FakeSession([FakeResponse(200, {"code": 0})])
    summary = SummaryResult(
        title="标题",
        summary="摘要",
        topics=["话题"],
        key_points=["要点"],
        quotes=["引用"],
    )
    write_document_content("doc-token", summary, "全文", "token", session=session)
    assert session.calls


def test_write_document_content_includes_shownote() -> None:
    session = FakeSession([FakeResponse(200, {"code": 0})])
    summary = SummaryResult(
        title="标题",
        summary="摘要",
        topics=[],
        key_points=[],
        quotes=[],
    )
    shownote = ShownoteContent(
        text="本期内容相关资料\n《凯利公式介绍》",
        images=["https://image.xyzcdn.net/chart.png"],
    )

    write_document_content("doc-token", summary, "全文", "token", session=session, shownote=shownote)

    children = session.calls[0][1]["json"]["children"]
    contents = [
        element["text_run"]["content"]
        for block in children
        for value in block.values()
        if isinstance(value, dict)
        for element in value.get("elements", [])
        if "text_run" in element
    ]
    assert "Shownote" in contents
    assert any("本期内容相关资料" in content for content in contents)
    assert any("《凯利公式介绍》" in content for content in contents)
    assert "图片: https://image.xyzcdn.net/chart.png" in contents


def test_publish_summary_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"feishu_app_id":"app-id","feishu_app_secret":"app-secret"}', encoding="utf-8")
    test_settings = get_settings(config_path)
    monkeypatch.setattr("src.media_tool.feishu.get_settings", lambda: test_settings)

    session = FakeSession(
        [
            FakeResponse(200, {"code": 0, "tenant_access_token": "token-1"}),
            FakeResponse(200, {"code": 0, "data": {"document": {"document_id": "doc-1"}}}),
            FakeResponse(200, {"code": 0}),
        ]
    )
    summary = SummaryResult(
        title="标题",
        summary="摘要",
        topics=[],
        key_points=[],
        quotes=[],
    )
    result = publish_summary(summary, "全文", session=session)
    assert result.doc_token == "doc-1"
    assert result.url == build_doc_url("doc-1")
