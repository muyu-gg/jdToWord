"""anchor.py — 给任意 Word 文档的「可改段落」埋内容控件锚点（一次性）。

原理：把每个目标段落包一层 content control（带 `@tag`），之后定制只改锚点里的文字，
字体/编号/图片/文本框/页眉页脚原样不动 —— 这就是「保结构」。

产出：
  <out-dir>/<name>          带锚点的模板（后续每次都基于它改）
  <out-dir>/docx_slots.json 槽位地图（tag -> 章节/标签/字数预算/是否可空）

用了哪个模板的哪些 paraId，由 `--slots` 传入的槽位配置决定（用 `jd2word discover` 查 paraId）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine import ooxml
from .slots import (
    DEFAULT_GROWTH,
    MIN_CHARS,
    build_slot_map,
    load_slots_config,
    save_slot_map,
)

# 埋锚点前后必须零变化的结构计数（content_control_count 除外，它会 +N）
_STABLE_COUNT_KEYS = (
    "parts_count",
    "paragraph_count",
    "table_count",
    "image_count",
    "field_count",
    "comment_count",
    "bookmark_count",
)


def anchor(
    template: str | Path,
    config_path: str | Path,
    out_dir: str | Path,
    name: str = "resume_template.docx",
    growth: float = DEFAULT_GROWTH,
    min_chars: int = MIN_CHARS,
) -> dict[str, Any]:
    template = Path(template)
    if not template.exists():
        raise FileNotFoundError(f"模板不存在：{template}")
    config_path = Path(config_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = out_dir / name
    out_slots = out_dir / "docx_slots.json"

    config = load_slots_config(config_path)

    # 定位键 / tag 唯一性校验（定位键 = paraId 或 paragraph_index）
    keys = [s.get("paraId") or f"idx:{s.get('paragraph_index')}" for s in config]
    tags = [s["tag"] for s in config]
    if len(set(keys)) != len(keys):
        dup = sorted({x for x in keys if keys.count(x) > 1})
        raise ValueError(f"槽位配置里有重复定位键：{dup}")
    if len(set(tags)) != len(tags):
        dup = sorted({x for x in tags if tags.count(x) > 1})
        raise ValueError(f"槽位配置里有重复 tag：{dup}")

    slots = build_slot_map(str(template), config, growth=growth, min_chars=min_chars)
    print(f"INFO: 解析到 {len(slots)} 个槽位")

    operations: list[dict[str, Any]] = []
    for s in slots:
        op: dict[str, Any] = {
            "op": "wrap_paragraph_with_content_control",
            "tag": s["tag"],
            "alias": s.get("label") or s["tag"],
            "lock": False,
        }
        # 优先按 paraId 定位；没有 paraId（如 python-docx 生成的文档）则退回 paragraph_index
        if s.get("paraId"):
            op["paraId"] = s["paraId"]
        else:
            op["paragraph_index"] = int(s["paragraph_index"])
        if s.get("current_sha256"):
            op["expected_old_text"] = s["current_text"]
            op["expected_old_sha256"] = s["current_sha256"]
        operations.append(op)

    patchset = {
        "schema_version": "1.1",
        "reason": "埋内容控件锚点（jdToWord anchor）",
        # 容器段落可能被内部校验误报，关闭 abort，改为事后自检
        "abort_on_validation_error": False,
        "overwrite": True,
        "operations": operations,
    }

    print("INFO: assess …")
    assess = ooxml.assess_patchset(str(template), patchset)
    if not assess.get("ok"):
        raise RuntimeError(f"assess 未通过：{assess.get('risks')}")

    print("INFO: apply …")
    ooxml.apply_patchset(str(template), patchset, output_path=str(out_template))

    print("INFO: 结构自检 …")
    b = ooxml.inspect_docx(str(template))
    a = ooxml.inspect_docx(str(out_template))
    for k in _STABLE_COUNT_KEYS:
        if b.get(k) != a.get(k):
            raise RuntimeError(f"结构计数变化 {k}: {b.get(k)} -> {a.get(k)}")
    if a.get("content_control_count") != len(slots):
        raise RuntimeError(f"控件数 {a.get('content_control_count')} != {len(slots)}")

    cc = ooxml.list_content_controls(str(out_template))
    got = {c.get("tag") for c in cc.get("content_controls", [])}
    missing = {s["tag"] for s in slots} - got
    if missing:
        raise RuntimeError(f"锚点缺失：{sorted(missing)}")

    save_slot_map(out_slots, slots, template=str(out_template), source=str(template))
    return {"template": str(out_template), "slots_map": str(out_slots), "slot_count": len(slots)}
