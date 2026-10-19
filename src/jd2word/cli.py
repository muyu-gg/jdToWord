"""cli.py — jd2word 命令行入口。

子命令：
    discover  <docx>                          列出 Word 段落（paraId/文本/样式）
    anchor    <docx> --slots S --out-dir D     给可改段落埋内容控件锚点（一次性）
    tailor    --slots M --fills F --jd-id ID   按 fills 定制 Word（保结构）
    verify    <output.docx> --slots M          交付前三查
    package   <docx> <work> <pkg> --slots M    打包交付
    ocr       --img X --out Y                  截图转文本（Windows 内置 OCR）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass


def _cmd_discover(args) -> int:
    from .discover import discover, format_table

    result = discover(args.docx, max_preview=args.max_preview)
    if args.emit_config:
        cfg = {
            "slots": [
                {
                    "paraId": p["paraId"],
                    "tag": f"slot.{i:02d}",
                    "section": "",
                    "label": (p.get("text_preview") or "")[:20],
                    "can_drop": False,
                }
                for i, p in enumerate(result["paragraphs"], start=1)
                if p.get("paraId")
            ]
        }
        Path(args.emit_config).write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已生成槽位配置草稿：{args.emit_config}（请删掉不需要的段、改好 tag/label 后再 anchor）")
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"文档：{result['docx']}  共 {result['count']} 段\n")
        print(format_table(result["paragraphs"]))
    return 0


def _cmd_anchor(args) -> int:
    from .anchor import anchor

    r = anchor(args.docx, args.slots, args.out_dir, name=args.name, growth=args.growth)
    print(f"OK: 带锚点模板 -> {r['template']}")
    print(f"OK: 槽位地图 -> {r['slots_map']}（{r['slot_count']} 槽，锚点校验通过）")
    return 0


def _cmd_tailor(args) -> int:
    from .tailor import tailor

    final = tailor(
        slots_map_path=args.slots,
        fills_path=args.fills,
        jd_id=args.jd_id,
        out_dir=args.out,
        publish_dir=args.publish,
    )
    planned = final.get("planned", [])
    changed = [p["tag"] for p in planned if p["changed"]]
    print(f"jd_id: {args.jd_id}")
    print(f"改动槽位: {len(changed)} / {len(planned)}")
    if args.verbose:
        for line in final.get("changelog", []):
            print("  " + line)
    elif changed:
        print("  槽位: " + ", ".join(changed))
    print(f"输出: {final.get('output_docx') or '(无改动)'}")
    if final.get("published"):
        print(f"已发布: {final['published']}")
    ok = final.get("validation_ok")
    print(f"结构校验: {'OK' if ok else 'FAILED'}")
    for i in final.get("validation_issues", []):
        print(f"  ⚠ {i['code']} | {i['message'][:160]}")
    return 0 if ok else 1


def _cmd_verify(args) -> int:
    from .verify import verify

    r = verify(
        args.output_docx,
        slots_map_path=args.slots,
        template=args.template,
        fills_path=args.fills,
        verbose=args.verbose,
    )
    return 0 if r["ok"] else 1


def _cmd_package(args) -> int:
    from .package import package

    package(args.output_docx, args.work_dir, args.package_dir, args.slots, make_zip=args.zip)
    return 0


def _cmd_ocr(args) -> int:
    from .ocr import ocr_image

    ocr_image(args.img, args.out)
    print(f"OK: 识别文本 -> {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="jd2word",
        description="输入岗位 JD/截图，分析后直接用 Word AI 改写你的 Word 简历（保结构、纯本地）",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("discover", help="列出 Word 段落（paraId/文本/样式）")
    p.add_argument("docx")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--max-preview", type=int, default=120)
    p.add_argument("--emit-config", metavar="PATH", help="生成槽位配置草稿（挑完段后再改）")
    p.set_defaults(func=_cmd_discover)

    p = sub.add_parser("anchor", help="给可改段落埋内容控件锚点（一次性）")
    p.add_argument("docx")
    p.add_argument("--slots", required=True, help="槽位配置 JSON")
    p.add_argument("--out-dir", required=True, help="输出目录（放模板 + 槽位地图）")
    p.add_argument("--name", default="resume_template.docx")
    p.add_argument("--growth", type=float, default=1.15, help="字数预算 = 原字数 × growth")
    p.set_defaults(func=_cmd_anchor)

    p = sub.add_parser("tailor", help="按 fills 定制 Word（保结构）")
    p.add_argument("--slots", required=True, help="槽位地图 JSON（anchor 产出）")
    p.add_argument("--fills", required=True, help="fills.json（Agent 产出的逐槽文本）")
    p.add_argument("--jd-id", required=True)
    p.add_argument("--out", required=True, help="输出目录")
    p.add_argument("--publish", default=None, help="额外发布副本到此目录")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=_cmd_tailor)

    p = sub.add_parser("verify", help="交付前三查")
    p.add_argument("output_docx")
    p.add_argument("--slots", required=True, help="槽位地图 JSON")
    p.add_argument("--template", default=None, help="默认取槽位地图里的 template")
    p.add_argument("--fills", default=None)
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("package", help="打包交付")
    p.add_argument("output_docx")
    p.add_argument("work_dir")
    p.add_argument("package_dir")
    p.add_argument("--slots", required=True)
    p.add_argument("--zip", action="store_true", help="额外生成同名 .zip")
    p.set_defaults(func=_cmd_package)

    p = sub.add_parser("ocr", help="截图转文本（Windows 内置 OCR）")
    p.add_argument("--img", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_ocr)

    return ap


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
