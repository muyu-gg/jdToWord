"""slots.py — 槽位（可改段落）配置与「槽位地图」读写。

概念：
  - **槽位配置**（slots config）：使用者/Agent 给的「哪些段落可改、叫什么」清单，形如
        {"slots": [{"paraId": "0DDB6DFB", "tag": "resume:name", "label": "姓名",
                    "section": "基本信息", "can_drop": false, "budget": 20}, ...]}
    `paraId` 由 `jd2word discover` 从实际 Word 里查得；`budget` 可省略（自动 = 现有字数 × growth）。

  - **槽位地图**（slots map）：`jd2word anchor` 产出的运行期映射，含每个槽的实测字数、
    字数预算 budget_chars、原文 current_text 及其 sha256，供 tailor / verify 使用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import ooxml

DEFAULT_GROWTH = 1.15
MIN_CHARS = 10


def load_slots_config(path: str | Path) -> list[dict[str, Any]]:
    """读槽位配置 JSON，返回 slots 列表。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    slots = data.get("slots") if isinstance(data, dict) else data
    if not isinstance(slots, list) or not slots:
        raise ValueError(f"槽位配置为空或格式不对：{path}（应为 {{\"slots\": [...]}}）")
    for s in slots:
        if not (s.get("paraId") or s.get("paragraph_index") is not None):
            raise ValueError(f"槽位缺 paraId / paragraph_index：{s}")
        if not s.get("tag"):
            raise ValueError(f"槽位缺 tag：{s}")
    return slots


def read_slot_paragraph(template: str, s: dict[str, Any]) -> dict[str, Any]:
    """按槽位配置读模板里对应段落（支持 paraId 或 paragraph_index）。"""
    if s.get("paraId"):
        return ooxml.read_paragraph(template, paraId=s["paraId"])
    return ooxml.read_paragraph(template, paragraph_index=int(s["paragraph_index"]))


def build_slot_map(
    template: str | Path,
    config: list[dict[str, Any]],
    growth: float = DEFAULT_GROWTH,
    min_chars: int = MIN_CHARS,
) -> list[dict[str, Any]]:
    """读模板实测每段字数，算字数预算，产出完整槽位地图。"""
    template = str(template)
    slots: list[dict[str, Any]] = []
    for s in config:
        key = s.get("paraId") or f"#idx={s.get('paragraph_index')}"
        try:
            info = read_slot_paragraph(template, s)
            cur = info.get("text", "") or ""
            sha = info.get("text_sha256", "")
        except Exception as e:  # noqa: BLE001
            print(f"WARN: 读不到 {key}（{s.get('label','?')}）：{e}")
            cur, sha = "", ""
        budget = int(s.get("budget") or max(min_chars, int(len(cur) * growth)))
        slots.append({**s, "budget_chars": budget, "current_text": cur, "current_sha256": sha})
    return slots


def save_slot_map(
    path: str | Path,
    slots: list[dict[str, Any]],
    template: str,
    source: str | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"template": str(template), "source": source, "slots": slots},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_slot_map(path: str | Path) -> dict[str, Any]:
    """读槽位地图，返回 {"template", "source", "slots"}。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_fills(path: str | Path) -> dict[str, Any]:
    """读 fills.json，返回 {tag: {"text":..., "alternates":[...]}}。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("slots", {}) or {}
