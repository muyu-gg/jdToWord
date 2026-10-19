"""discover.py — 列出任意 Word 文档里的全部段落（paraId / 文本 / 样式）。

这是「给任意用户的 Word 简历埋锚点」的第一步：先看清楚文档里有哪些段，
挑出「可以改」的段（如 求职意向 / 各项目要点 / 技术栈），再去 anchor。

用法：
    jd2word discover 我的简历.docx
    jd2word discover 我的简历.docx --json > 段落清单.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine import ooxml


def list_paragraphs(docx: str | Path, max_preview: int = 120) -> list[dict[str, Any]]:
    """返回段落清单（含 paraId），已过滤空段。"""
    info = ooxml.list_paragraphs(str(docx), max_preview=max_preview, include_empty=False)
    return info.get("paragraphs", [])


def discover(docx: str | Path, max_preview: int = 120) -> dict[str, Any]:
    docx = Path(docx)
    if not docx.exists():
        raise FileNotFoundError(f"文档不存在：{docx}")
    paras = list_paragraphs(docx, max_preview=max_preview)
    return {"docx": str(docx), "count": len(paras), "paragraphs": paras}


def format_table(paras: list[dict[str, Any]]) -> str:
    """把段落清单排成人可读的表格。"""
    lines = [
        f"{'#':>4}  {'paraId':<10}  {'样式':<14}  文本预览",
        "-" * 88,
    ]
    for p in paras:
        idx = p.get("paragraph_index", "")
        pid = p.get("paraId") or "(无)"
        style = (p.get("style_name") or p.get("style_id") or "")[:14]
        preview = (p.get("text_preview") or "").replace("\n", " ").replace("\t", " ")
        in_cc = p.get("content_control_tag")
        mark = f" [{in_cc}]" if in_cc else ""
        lines.append(f"{idx:>4}  {pid:<10}  {style:<14}  {preview}{mark}")
    return "\n".join(lines)
