"""package.py — 把定制 docx + 改动说明打包成一个交付文件夹。

交付物：<package_dir>/ 内含
  - <jd_id>.docx        定制后的 Word 简历
  - changelog.md        逐槽「原 → 新」改动列表
  - 匹配分析.md         若调用方已放该目录（可选）会被一起带上
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from .slots import load_slot_map


def _write_changelog(work: Path, out_docx: Path, slots_map: Path) -> None:
    lines = ["# 改动列表", ""]
    fills_path = work / "fills.json"
    if slots_map.exists() and fills_path.exists():
        by_tag = {s["tag"]: s for s in load_slot_map(slots_map)["slots"]}
        fills = json.loads(fills_path.read_text(encoding="utf-8")).get("slots", {})
        for tag, spec in fills.items():
            s = by_tag.get(tag)
            if not s:
                continue
            new = str((spec or {}).get("text", ""))
            old = s.get("current_text", "")
            if new == old:
                continue
            lines += [
                f"## {s.get('section','')} · {s.get('label','')}（{tag}）",
                f"- 原：{old}",
                f"- 新：{new}",
                "",
            ]
        (work / "changelog.md").write_text("\n".join(lines), encoding="utf-8")
    else:
        print("WARN: 缺少槽位地图或 fills.json，changelog 可能为空")


def package(
    output_docx: str | Path,
    work_dir: str | Path,
    package_dir: str | Path,
    slots_map: str | Path,
    make_zip: bool = False,
) -> Path:
    out_docx = Path(output_docx)
    work = Path(work_dir)
    pkg = Path(package_dir)
    slots_map = Path(slots_map)

    _write_changelog(work, out_docx, slots_map)

    pkg.mkdir(parents=True, exist_ok=True)
    for f in [out_docx, work / "匹配分析.md", work / "changelog.md"]:
        if Path(f).exists():
            shutil.copy2(f, pkg / Path(f).name)
    print("打包目录:", pkg)
    for f in sorted(pkg.iterdir()):
        print("  -", f.name)

    zip_path = pkg.with_suffix(".zip")
    if make_zip:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in pkg.iterdir():
                z.write(f, f.name)
        print("压缩包:", zip_path)
    elif zip_path.exists():
        zip_path.unlink()
    return pkg
