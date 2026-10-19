---
name: jd-to-word
description: 输入岗位 JD（文字或截图）→ 分析匹配度 → 用 Word AI 直接改写你的 Word 简历（保结构、纯本地）。当用户给出 JD、岗位截图，并希望修改/定制自己的 Word(.docx) 简历时使用。
---

# jd-to-word · JD 直改 Word 简历

把「JD → 分析 → 改写 Word 简历」串成一条流水线：**智能部分由你（Agent）做，确定性部分由 `jd2word` 脚本做**。

> **纯本地**：全程不联网、不上传简历/JD/文档；所有产物只写在本机。

---

## ⛔ 伦理红线（违反即停止）

- ❌ 不凭空新增简历里没有的项目、技能、公司、经历
- ❌ 不编造数字（用户量、增长率、营收…），缺就在改写里留白，**不臆造**
- ❌ 不改工作时间段、职级、公司名
- ✅ 只做**重排 / 精简 / 换措辞**；每一处改动都写进 changelog，可逐条核对

---

## 前置：环境自检（一条命令）

```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
jd2word --help            # 或 python -m jd2word.cli --help
```

若报「找不到 Word AI 引擎」→ 先按 README 安装第三方依赖 word-ai，并设 `WORDAI_DIR`。

---

## 首次使用：给用户的 Word 简历埋锚点（一次性）

1. **看有哪些段**（找出可改的段）：
   ```bash
   jd2word discover "用户的简历.docx" --emit-config slots.json
   ```
   编辑 `slots.json`：**删掉不改的段**，给保留的段起好 `tag`（如 `resume:intent`、`resume:proj.a.b1`）与 `label`；
   项目要点类段可设 `"can_drop": true`（允许清空）；求职意向这类长短不一的段可手给 `"budget": 20`。

2. **埋锚点**：
   ```bash
   jd2word anchor "用户的简历.docx" --slots slots.json --out-dir .wordai
   ```
   产出 `.wordai/resume_template.docx`（基准模板）+ `.wordai/docx_slots.json`（槽位地图）。之后每次定制都基于它。

> 换简历 / 模板大改后重跑这两步。

---

## 单份 JD 的定制流程

**第 1 步 · 拿到 JD 文本**
- JD 是文字 → 直接用。
- JD 是截图 → **只走 OCR**，绝不 `Read` 原图（图片会随每轮重发，极耗 token）：
  ```bash
  jd2word ocr --img "岗位截图.png" --out jd.txt
  ```
  然后只读 `jd.txt`。

**第 2 步 · 分析（你来做）**
读 JD + 用户简历母版 + 槽位地图，产出一份**匹配分析**：JD 关键要求 → 简历里哪段最能命中 → 哪个项目强化 / 哪个弱化。

**第 3 步 · 写 `fills.json`（你来做）**
只写**要改**的槽；未出现的槽 = 不动。
```json
{
  "jd_id": "ai-intern",
  "slots": {
    "resume:intent":    { "text": "求职意向：AI 开发实习生" },
    "resume:skill.pro": { "text": "专业技能：…", "alternates": ["更短的备选…"] },
    "resume:proj.a.b2": { "text": "" }
  }
}
```
规则：
- `text` 是**填好后的完整文字**（含原前缀，如 `求职意向：`、`▸ `）；
- 长度要 ≤ 槽位地图里的 `budget_chars`，放不下就写 `alternates`（依次备选）；实在都放不下脚本会按标点截断；
- `""` = 清空（仅 `can_drop=true` 的槽）；
- **只重排/精简/改写，不新增事实、不编数字。**

**第 4 步 · 落地（脚本做）**
```bash
jd2word tailor --slots .wordai/docx_slots.json --fills fills.json \
  --jd-id ai-intern --out out/ai-intern
```
看到 **`结构校验: OK`** 才算成功；`FAILED` 就照问题行排查，**不要谎报成功**。

**第 5 步 · 三查交付**
```bash
jd2word verify out/ai-intern/ai-intern.docx --slots .wordai/docx_slots.json \
  --fills fills.json
```
默认三行即过：① 结构计数全等 ② 未改动槽 == 模板原文 ③ 目标槽回读 == fills（无截断）。

**第 6 步 ·（可选）打包**
```bash
jd2word package out/ai-intern/ai-intern.docx out/ai-intern 交付-ai-intern \
  --slots .wordai/docx_slots.json
```

---

## 完成报告（给用户）

- 改了哪些槽（`tag` → 新文本摘要）
- 输出 docx 的**本地路径**
- 三查结果（OK / 具体问题）
- 提醒：**Word 里打开前先关掉同名文件**，避免占用导致写入失败。
