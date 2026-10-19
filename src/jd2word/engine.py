"""engine.py — 定位并加载 Word AI 引擎（`word_ai_mcp`）。

Word AI 是第三方开源项目（flyfish-dev/word-ai，AGPL-3.0-or-later），
**源码不包含在本仓库中**，需由使用者自行安装。本模块只负责把它找到并暴露 `ooxml` 运行时。

查找顺序：
  1. 当前 Python 环境已安装的 `word_ai_mcp`（pip 装 / venv 装均可）；
  2. 环境变量 `WORDAI_DIR`（或 `WORDAI`）指向的目录；
  3. 本项目同级 / 上级的 `tools/word-ai`（开发机常见布局）。

用法：
    from jd2word.engine import ooxml
    ooxml.inspect_docx("a.docx")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

_INSTALL_HINT = (
    "找不到 Word AI 引擎（word_ai_mcp）。\n"
    "请先安装第三方依赖 word-ai（AGPL-3.0）：\n"
    "    git clone https://github.com/flyfish-dev/word-ai\n"
    "    然后设置环境变量指向它：WORDAI_DIR=/path/to/word-ai\n"
    "或者直接 pip install 到当前环境。详见 README「安装」。"
)


def _candidate_dirs() -> list[Path]:
    out: list[Path] = []
    for env in ("WORDAI_DIR", "WORDAI"):
        v = os.environ.get(env)
        if v:
            out.append(Path(v))
    here = Path(__file__).resolve()
    for up in here.parents:
        out.append(up / "tools" / "word-ai")
    return out


def load_ooxml() -> ModuleType:
    """返回 `word_ai_mcp.ooxml` 模块；找不到时抛出带安装指引的 RuntimeError。"""
    try:
        from word_ai_mcp import ooxml  # type: ignore

        return ooxml
    except Exception:  # noqa: BLE001 - 未安装则继续找本地目录
        pass

    for cand in _candidate_dirs():
        if (cand / "word_ai_mcp" / "ooxml.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            try:
                from word_ai_mcp import ooxml  # type: ignore

                return ooxml
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"{_INSTALL_HINT}\n（导入 {cand} 失败：{e}）") from e

    raise RuntimeError(_INSTALL_HINT)


def _lazy() -> ModuleType:
    return load_ooxml()


class _LazyOoxml:
    """延迟加载：`from jd2word.engine import ooxml` 时不立刻 import，直到真正用到。"""

    _mod: ModuleType | None = None

    def __getattr__(self, name: str):
        if self._mod is None:
            self._mod = _lazy()
        return getattr(self._mod, name)


ooxml = _LazyOoxml()  # type: ignore[assignment]
