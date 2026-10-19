"""tailor.py — JD 定制 Word 简历的确定性工作流（LangGraph）。

分工：
  - **智能**（读 JD + 从母版选内容 + 改写措辞）由 Agent 在调用本模块前完成，写成 fills.json；
  - **确定性**（按预算裁剪 → 生成 PatchSet → 保结构写入 → 自检）由本模块完成。

节点：load_slots → load_fills → fit_budget → build_patchset → apply → validate → finalize

fills.json 结构：
  {"jd_id": "<id>", "slots": {"resume:intent": {"text": "...", "alternates": ["更短的备选"]}}}
  - 未出现的 slot = 不改动
  - text 为空串 "" = 清空该槽（仅 can_drop=true 的槽允许）
  - alternates = 放不下时的依次备选（优先级由顺序体现）
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .engine import ooxml
from .slots import load_slot_map


class WFState(TypedDict, total=False):
    slots_map_path: str
    fills_path: str
    jd_id: str
    out_dir: str
    publish_dir: str | None
    template: str
    slots: list
    fills: dict
    planned: list
    patchset: dict
    output_docx: str
    validation_ok: bool
    validation_issues: list
    changelog: list
    published: str


def _truncate(text: str, budget: int) -> tuple[str, bool]:
    """按预算裁剪，尽量在标点/空格处断句。返回 (文本, 是否被裁)。"""
    if len(text) <= budget:
        return text, False
    head = text[:budget]
    for ch in "。！？；，、,.!?; /|":
        idx = head.rfind(ch)
        if idx >= max(4, budget // 2):
            return head[: idx + 1], True
    return head, True


# ---- 节点 -------------------------------------------------------------------
def node_load_slots(state: WFState) -> WFState:
    data = load_slot_map(state["slots_map_path"])
    template = data["template"]
    slots = data["slots"]
    if not Path(template).exists():
        raise FileNotFoundError(f"带锚点模板不存在：{template}（先跑 jd2word anchor）")
    cc = ooxml.list_content_controls(template)
    got = {c.get("tag") for c in cc.get("content_controls", [])}
    missing = [s["tag"] for s in slots if s["tag"] not in got]
    if missing:
        raise ValueError(f"模板缺少锚点：{missing}")
    state["template"] = template
    state["slots"] = slots
    return state


def node_load_fills(state: WFState) -> WFState:
    p = Path(state["fills_path"])
    if not p.exists():
        raise FileNotFoundError(f"fills.json 不存在：{p}")
    state["fills"] = json.loads(p.read_text(encoding="utf-8")).get("slots", {}) or {}
    return state


def node_fit_budget(state: WFState) -> WFState:
    planned: list[dict] = []
    fills = state["fills"]
    for s in state["slots"]:
        tag = s["tag"]
        budget = int(s.get("budget_chars") or 0)
        cur = s.get("current_text", "") or ""
        if tag not in fills:
            continue  # 不改动
        spec = fills[tag] or {}
        cands: list[str] = []
        if spec.get("text") is not None:
            cands.append(str(spec["text"]))
        for a in spec.get("alternates") or []:
            cands.append(str(a))

        new_text = cur
        if cands:
            chosen = next((c for c in cands if len(c) <= budget), None)
            if chosen is None:
                chosen = _truncate(cands[0], budget)[0]
            new_text = chosen
        else:
            new_text = "" if s.get("can_drop") else cur

        planned.append(
            {
                "tag": tag,
                "paraId": s.get("paraId", ""),
                "can_drop": s.get("can_drop", False),
                "old_text": cur,
                "new_text": new_text,
                "changed": new_text != cur,
            }
        )
    state["planned"] = planned
    return state


def node_build_patchset(state: WFState) -> WFState:
    ops = []
    for p in state["planned"]:
        if not p["changed"]:
            continue
        op: dict[str, Any] = {
            "op": "replace_content_control_text",
            "tag": p["tag"],
            "text": p["new_text"],
            "preserve_style": True,
            "allow_paragraph_count_change": False,
        }
        if p.get("old_text"):
            op["expected_old_text"] = p["old_text"]
        ops.append(op)
    state["patchset"] = {
        "schema_version": "1.1",
        "reason": f"JD 定制：{state['jd_id']}",
        "abort_on_validation_error": False,
        "overwrite": True,
        "operations": ops,
    }
    return state


def node_apply(state: WFState) -> WFState:
    ops = state["patchset"]["operations"]
    if not ops:
        state["output_docx"] = ""
        state["validation_ok"] = True
        state["validation_issues"] = []
        return state
    out_dir = Path(state["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_docx = out_dir / f"{state['jd_id']}.docx"
    ooxml.apply_patchset(state["template"], state["patchset"], output_path=str(out_docx))
    state["output_docx"] = str(out_docx)
    return state


def node_validate(state: WFState) -> WFState:
    if not state.get("output_docx"):
        return state
    issues: list[dict] = []
    b = ooxml.inspect_docx(state["template"])
    a = ooxml.inspect_docx(state["output_docx"])
    for k in (
        "parts_count", "paragraph_count", "table_count", "image_count",
        "field_count", "comment_count", "content_control_count", "bookmark_count",
    ):
        if b.get(k) != a.get(k):
            issues.append({"code": "count_changed", "message": f"{k}: {b.get(k)} -> {a.get(k)}"})
    for p in state["planned"]:
        if not p["changed"]:
            continue
        got = ooxml.get_content_control_text(state["output_docx"], p["tag"]).get("text", "") or ""
        if got != p["new_text"]:
            issues.append(
                {"code": "slot_mismatch", "message": f"{p['tag']}: 期望「{p['new_text']}」实得「{got}」"}
            )
    state["validation_ok"] = not issues
    state["validation_issues"] = issues
    return state


def node_finalize(state: WFState) -> WFState:
    state["changelog"] = [
        f"[{p['tag']}] 「{p['old_text']}」 -> 「{p['new_text']}」"
        for p in state["planned"] if p["changed"]
    ]
    if state.get("publish_dir") and state.get("output_docx"):
        pub = Path(state["publish_dir"])
        pub.mkdir(parents=True, exist_ok=True)
        dst = pub / Path(state["output_docx"]).name
        shutil.copy2(state["output_docx"], dst)
        state["published"] = str(dst)
    return state


def build_graph():
    g = StateGraph(WFState)
    g.add_node("load_slots", node_load_slots)
    g.add_node("load_fills", node_load_fills)
    g.add_node("fit_budget", node_fit_budget)
    g.add_node("build_patchset", node_build_patchset)
    g.add_node("apply", node_apply)
    g.add_node("validate", node_validate)
    g.add_node("finalize", node_finalize)
    g.add_edge(START, "load_slots")
    g.add_edge("load_slots", "load_fills")
    g.add_edge("load_fills", "fit_budget")
    g.add_edge("fit_budget", "build_patchset")
    g.add_edge("build_patchset", "apply")
    g.add_edge("apply", "validate")
    g.add_edge("validate", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def tailor(
    slots_map_path: str | Path,
    fills_path: str | Path,
    jd_id: str,
    out_dir: str | Path,
    publish_dir: str | Path | None = None,
) -> WFState:
    app = build_graph()
    init: WFState = {
        "slots_map_path": str(slots_map_path),
        "fills_path": str(fills_path),
        "jd_id": jd_id,
        "out_dir": str(out_dir),
        "publish_dir": str(publish_dir) if publish_dir else None,
    }
    return app.invoke(init)
