# jdToWord · 让岗位 JD 直接改写你的 Word 简历

**输入一段 JD（或一张岗位截图）→ 自动分析匹配度 → 直接把你自己的 Word 简历改好，版式一字不动。**

作者：**muyu-gg**

> 纯本地运行：不联网、不上传简历/JD/文档，所有文件只存在你的电脑里。

---

## 它解决什么问题

大多数 AI 改简历工具的做法是「把 Word 转成文本 → 让 AI 重写 → 再导出成一份**新的** Word」。
结果是**版式全毁**：字体、行距、项目符号、表格、文本框、页眉页脚全乱套。

jdToWord 走另一条路：**不改版式，只换文字**。

- 先给你的简历「埋锚点」——把可改的段落（求职意向、各项目要点、技术栈…）各自包一层内容控件；
- 之后每次定制，**只替换锚点里的文字**；
- 写完自动**结构自检**：段落/表格/图片/域/控件等计数必须**零变化**，并通过「三查」才交付。

所以每次产出的都是一份**和原版长得一模一样、但内容对准了 JD** 的简历。

---

## 核心能力

| 子命令 | 作用 |
|---|---|
| `jd2word discover` | 列出任意 Word 里所有段落（paraId / 文本 / 样式），挑出「可改段」 |
| `jd2word anchor` | 给可改段埋内容控件锚点（一次性），产出带锚点模板 + 槽位地图 |
| `jd2word tailor` | 按 `fills.json` 定制 Word（保结构改文字） |
| `jd2word verify` | 交付前「三查」：结构零变化 / 未改槽不动 / 目标槽无截断 |
| `jd2word package` | 打包交付（docx + 改动说明） |
| `jd2word ocr` | 截图转文本（Windows 内置 OCR，离线） |

**智能在 Agent，确定性在脚本**：读 JD、挑项目、改措辞由 AI Agent 完成，写成 `fills.json`；按预算裁剪、写 Word、自检、打包由脚本完成，可复现、可审计。

---

## 安装

### 1. 本工具

```bash
git clone https://github.com/muyu-gg/jdToWord
cd jdToWord
pip install -e .
```

### 2. 第三方依赖：Word AI（必需）

jdToWord 的「保结构写 Word」能力来自开源项目 **Word AI**（作者 [flyfish-dev](https://github.com/flyfish-dev/word-ai)，AGPL-3.0）。
它**不包含在本仓库中**，需要你自行安装：

```bash
git clone https://github.com/flyfish-dev/word-ai
pip install lxml python-docx langgraph
```

然后让 jdToWord 找到它（任选一种）：

```bash
# 方式一：设环境变量（推荐）
export WORDAI_DIR=/path/to/word-ai        # Windows: set WORDAI_DIR=D:\path\to\word-ai

# 方式二：装到当前 Python 环境
pip install -e /path/to/word-ai
```

### 3. 自检

```bash
jd2word --help
jd2word discover 你的简历.docx        # 能打印段落即环境就绪
```

---

## 用法（5 步）

```bash
# ① 看有哪些可改段（同时生成槽位配置草稿）
jd2word discover 我的简历.docx --emit-config slots.json

# ② 编辑 slots.json：删掉不改的段、给保留的段起 tag/label；然后埋锚点（一次性）
jd2word anchor 我的简历.docx --slots slots.json --out-dir .wordai

# ③ 由 AI Agent 读 JD、生成 fills.json（或用 SKILL.md 里的 Agent 流程）

# ④ 落地（保结构改 Word）
jd2word tailor --slots .wordai/docx_slots.json --fills fills.json \
  --jd-id ai-intern --out out/ai-intern

# ⑤ 交付前三查
jd2word verify out/ai-intern/ai-intern.docx --slots .wordai/docx_slots.json --fills fills.json
```

JD 是截图时，先 OCR 成文本再交给流程：

```bash
jd2word ocr --img 岗位截图.png --out jd.txt
```

### 配合 AI Agent 使用

仓库自带 `skills/jd-to-word/SKILL.md`——把它放进你的 Agent（Claude Code / Codex 等）的 skill 目录，
Agent 就会自动完成「读 JD → 分析 → 写 fills.json → 调脚本 → 三查」的完整链路。

---

## 目录结构

```
jdToWord/
├── src/jd2word/
│   ├── engine.py     定位/加载 Word AI 引擎
│   ├── discover.py   列出 Word 段落
│   ├── anchor.py     埋内容控件锚点
│   ├── slots.py      槽位配置 / 槽位地图
│   ├── tailor.py     LangGraph 定制工作流
│   ├── verify.py     交付三查
│   ├── package.py    打包交付
│   ├── ocr.py        截图 OCR（Windows）
│   └── cli.py        命令行入口
├── skills/jd-to-word/SKILL.md   Agent 入口
└── docs/流程.md                  全流程说明
```

---

## 设计边界

- **不自动投递**：只产简历，投递由你手动完成。
- **不做格式转换**：不改版式、不搬移整块段落——正是因为「不许动结构」，才能保证版式不坏。
- **不改事实**：不新增简历里没有的经历/技能，不编数字，不改时间段/职级/公司名。
- **截图 OCR 仅 Windows**：用的是系统自带识别引擎；非 Windows 用户先把截图转成文本再喂进流程。

---

## 隐私

- 全部逻辑在本地运行，**不连接任何第三方服务器**，不上传简历、JD 或文档；
- 不做数据采集、无遥测；
- 所有输入与产物只保存在你的本机。
- 本仓库**不含任何用户数据**：`*.docx`、`.work/`、`out/` 等已在 `.gitignore` 中排除。

---

## 许可证与致谢

**Copyright (C) 2026 muyu-gg** · 本项目采用 [GNU AGPL-3.0-or-later](LICENSE)。

本仓库全部源码由 muyu-gg 编写。它调用第三方开源项目 **Word AI**（作者 flyfish-dev，AGPL-3.0-or-later）完成 DOCX 结构保留编辑——该依赖**不在本仓库内**，需自行安装。为与其许可证保持一致，本项目同样采用 AGPL-3.0-or-later。详见 [NOTICE](NOTICE)。
