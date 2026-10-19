"""verify.py — 交付前「三查」，固化交付质量。

三查：
  ① 结构计数全等        parts/paragraph/table/image/field/comment/bookmark/content_control
  ② 未改动槽 == 模板原文  （等价于「diff 只出现在目标槽」）
  ③ 目标槽回读 == fills 文本（证明新文字未被预算截断）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import ooxml
from .slots import load_slot_map

COUNT_KEYS = (
    "parts_count",
    "paragraph_count",
    "table_count",
    "image_count",
    "field_count",
    "comment_count",
    "bookmark_count",
    "content_control_count",
)


def _cc_text(docx: str, tag: str) -> str:
    r = ooxml.get_content_control_text(docx, tag)
    return (r.get("text", "") if isinstance(r, dict) else r) or ""


def verify(
    output_docx: str | Path,
    slots_map_path: str | Path,
    template: str | Path | None = None,
    fills_path: str | Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    O = str(output_docx)
    slots_data = load_slot_map(slots_map_path)
    T = str(template or slots_data["template"])
    slots = slots_data["slots"]
    fails: list[str] = []

    # ① 结构计数零变化
    b, a = ooxml.inspect_docx(T), ooxml.inspect_docx(O)
    bad = [f"{k}:{b.get(k)}->{a.get(k)}" for k in COUNT_KEYS if b.get(k) != a.get(k)]
    print("① 结构计数: " + ("OK（全等）" if not bad else "FAIL " + "; ".join(bad)))
    fails += bad

    # ②③ 逐槽比对
    fills: dict[str, Any] = {}
    if fills_path and Path(fills_path).exists():
        fills = json.loads(Path(fills_path).read_text(encoding="utf-8")).get("slots", {}) or {}

    n_target = n_untouched = 0
    bad_untouched: list[str] = []
    bad_target: list[str] = []
    for s in slots:
        tag = s["tag"]
        got = _cc_text(O, tag)
        if tag in fills:
            want = str((fills[tag] or {}).get("text", ""))
            n_target += 1
            if got != want:
                bad_target.append(f"{tag}: 期望「{want[:40]}」实得「{got[:40]}」")
        else:
            want = s.get("current_text", "") or ""
            n_untouched += 1
            if got != want:
                bad_untouched.append(f"{tag}: 期望「{want[:40]}」实得「{got[:40]}」")
        if verbose:
            print(f"   [{'OK ' if got == want else 'FAIL'}] {tag} len={len(got)}")

    ok_u = n_untouched - len(bad_untouched)
    ok_t = n_target - len(bad_target)
    print(f"② 未改动槽: {'OK' if not bad_untouched else 'FAIL'}（{ok_u}/{n_untouched} 与模板原文一致）")
    print(f"③ 目标槽回读: {'OK' if not bad_target else 'FAIL'}（{ok_t}/{n_target} 与 fills 一致，无截断）")
    for m in bad_untouched + bad_target:
        print("   ⚠ " + m)
    fails += bad_untouched + bad_target

    ok = not fails
    print("三查: " + ("全部 OK ✅" if ok else f"{len(fails)} 处问题 ❌"))
    return {"ok": ok, "fails": fails}
