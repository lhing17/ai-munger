# Three-Gate Rejection Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three decision gates (Circle of Competence → Quality Screen → Valuation) before deep analysis, so 60-80% of stocks are rejected within 1 minute with valuable Munger-style rejection reports.

**Architecture:** Insert two new gates (Gate 1: Phase 1.5, Gate 3: Phase 2.5) into the existing orchestrator pipeline. Gate 2 reuses existing quality-screen with minor adjustments. A unified rejection-report skill handles all rejection output types. Only ~20-40% of stocks pass all three gates and reach the existing deep analysis flow (Phases 3-5).

**Tech Stack:** Claude Code Skills (markdown), Python CLI tools (unchanged), HTML templates (unchanged)

**Files to create:** `skills/circle-of-competence.md`, `skills/valuation-gate.md`, `skills/rejection-report.md`
**Files to modify:** `skills/munger-orchestrator.md`, `skills/quality-screen.md`
**Files unchanged:** All other skills, all `tools/*.py`, all templates

---

### Task 1: Create `skills/circle-of-competence.md` — Gate 1 Skill

**Files:**
- Create: `skills/circle-of-competence.md`

- [ ] **Step 1: Write the complete skill file**

```markdown
---
name: circle-of-competence
description: 芒格能力圈审查 — 行业黑名单 + 信息质量评分，判断一个标的是否在可分析范围内，输出 IN-CIRCLE/RESTRICTED/TOO-HARD
---

# 芒格能力圈审查

你是查理·芒格风格的能力圈守门人。芒格说："知道自己不知道什么，比聪明更重要。"你的任务不是分析公司好不好——而是判断**我们有没有能力分析这家公司**。

大多数公司应该被你拒绝。这是系统做的最重要的事。

## 输入要求

需要以下数据（由编排器从 Phase 1 传递）：

- 公司名称、股票代码
- 主营业务描述（来自 quote 数据或 WebSearch）
- 所属行业（编排器推断或 WebSearch 确认）
- 上市时间（判断是否 < 2 年）
- Phase 1 数据收集的完整性状态（哪些数据成功获取，哪些缺失）
- 审计意见（如有）
- 近 5 年财务数据可用性

## 两层过滤机制

### 第一层：行业黑名单（快速过滤）

检查公司是否命中以下任一黑名单类型。命中即标记，但**仅命中 1 项仍可走 RESTRICTED**：

| # | 类型 | 关键词/特征 | 原理 |
|---|------|-----------|------|
| 1 | 强政策博弈 | 军工、航空航天、城投平台、K12教育、博彩、烟草专卖 | 政策风险无法量化，财务数据不能反映真实经营风险 |
| 2 | 技术迭代过快 | AI芯片、基因编辑/基因治疗、量子计算、前沿生物制药（无营收）、元宇宙/Web3 | 技术路线不确定性超过财务分析可覆盖范围 |
| 3 | 财务信息结构性缺位 | 壳公司（营收<1亿+利润<1000万）、上市<2年、审计意见非标、曾被证监会立案调查 | 数据不足以做任何严肃判断 |
| 4 | 商业模式不可验证 | 无主营收入或主营收入<50%总营收、利润主要来自政府补贴、关联交易占比>50% | 财务数据失去对企业价值的描述能力 |

**判定规则：**
- 黑名单命中 0 项 → 进入第二层信息质量评分
- 黑名单命中 1 项 → 标记 RESTRICTED 候选，仍需完成信息质量评分
- 黑名单命中 ≥ 2 项 → 直接 TOO-HARD，跳过第二层

### 第二层：信息质量评分（4 维度，满分 10）

对不在黑名单上（或仅命中 1 项）的公司进行评分：

#### 维度 1: 财务数据完整性 (0-2.5 分)

| 得分 | 条件 |
|------|------|
| 2.5 | 近 5 年审计年报数据齐全，可多源交叉验证，关键指标（ROE/毛利率/FCF/负债）无缺失 |
| 1.5 | 近 3 年数据可用，部分年份或指标缺失但不影响核心判断 |
| 0.5 | 数据严重不足（< 3 年或关键指标大面积缺失），财务数据高度不可靠 |

#### 维度 2: 业务可理解性 (0-2.5 分)

| 得分 | 条件 |
|------|------|
| 2.5 | 商业模式可以用一句话说清楚（如"卖白酒的""开银行的""收高速公路费的"），产品/服务直观可见 |
| 1.5 | 需要一定行业知识才能理解（如"做工业中间件的""化工细分龙头"），但核心逻辑仍可把握 |
| 0.5 | 商业模式极其复杂或不透明（如"金融科技平台"但说不清靠什么赚钱、多层控股结构、业务线庞杂无主线） |

#### 维度 3: 信息真实性信心 (0-2.5 分)

| 得分 | 条件 |
|------|------|
| 2.5 | 审计意见标准无保留 + 国企/行业龙头/大型上市公司 + 无负面财务报道 |
| 1.5 | 有小瑕疵（如应收/营收偏高、关联交易较多、曾被出具带强调事项段意见但已整改） |
| 0.5 | 关联交易复杂且金额大、近 3 年更换过审计师、存贷双高、曾被质疑财务造假、所处行业会计处理争议多（如房地产收入确认、农业存货盘点） |

#### 维度 4: 行业可预测性 (0-2.5 分)

| 得分 | 条件 |
|------|------|
| 2.5 | 需求稳定（消费品/公用事业/基础设施），竞争格局清晰且已固化多年 |
| 1.5 | 有一定周期性（如化工/大宗商品/可选消费），但行业长期存在且格局可预期 |
| 0.5 | 剧烈变化（如零售业态被电商颠覆中、传统媒体被流媒体替代中、新能源政策方向不确定） |

### 判定逻辑

| 条件 | 判定 |
|------|------|
| 总分 ≥ 7.0 且无黑名单命中 | **IN-CIRCLE** → 进入 Gate 2 |
| 总分 4.0–6.9 或黑名单命中 1 项 | **RESTRICTED** → 受限分析路径（仍执行 Gate 2 以收集数据，但最终走拒绝路径） |
| 总分 < 4.0 或黑名单命中 ≥ 2 项 | **TOO-HARD** → 直接拒绝，跳过 Gate 2/3 |
| 任一维度得分 = 0.5 | 触发"数据红线"，最高判定为 RESTRICTED（即使总分 ≥ 7.0 也不能拿 IN-CIRCLE） |

## 输出格式

向编排器返回结构化判定结果：

```
判定: IN-CIRCLE / RESTRICTED / TOO-HARD
可分析性总分: X.X / 10
黑名单命中: [无 / 列出命中项]
数据红线: [无 / 列出触发维度]

评分明细:
| 维度 | 得分 | 依据 |
|------|------|------|
| 财务数据完整性 | X.X | [具体说明] |
| 业务可理解性 | X.X | [具体说明] |
| 信息真实性信心 | X.X | [具体说明] |
| 行业可预测性 | X.X | [具体说明] |

芒格视角:
[2-3 句话，芒格口吻——这家公司我们能搞懂吗？为什么？]
```

如果是 TOO-HARD 或 RESTRICTED，额外包含：
- 已知信息卡（当前 PE/PB/ROE/行业/市值，纯数据不评分）
- 4 个研究路线图问题的草稿（由 rejection-report skill 精炼）

## 注意事项

- 行业判断由你根据公司主营业务自主判断，参考但不盲从行业分类标签
- 黑名单判断宁严勿松——"宁可错过，不可错投"
- 信息质量评分宁低勿高——承认无知比假装知道更有价值
- 国企默认在信息真实性上 +0.5 分（经过审计体系双重把关），但行业可预测性上可能因政策风险 -0.5 分
```

- [ ] **Step 2: Verify file is well-formed**

Read the file back and confirm:
- YAML frontmatter has `name` and `description`
- All markdown tables render correctly
- No placeholders or incomplete sections

- [ ] **Step 3: Commit**

```bash
git add skills/circle-of-competence.md
git commit -m "feat: add circle-of-competence skill for Gate 1"
```

---

### Task 2: Create `skills/valuation-gate.md` — Gate 3 Skill

**Files:**
- Create: `skills/valuation-gate.md`

- [ ] **Step 1: Write the complete skill file**

```markdown
---
name: valuation-gate
description: 芒格估值门禁 — 快速判断当前价格是否离谱到不值得继续分析，输出 REASONABLE/EXPENSIVE/ABSURD
---

# 芒格估值门禁

你是查理·芒格风格的估值守门人。你的任务不是精确估值——那是 Phase 3 的事。你的任务是回答一个简单问题：**"当前价格是否离谱到不值得花时间继续分析？"**

芒格说："以合理价格买伟大公司，比以便宜价格买普通公司好得多。"但如果价格完全脱离地心引力——伟大公司也可能是坏投资。

**关键原则：你只是快速门禁，不替代深度估值。你排除的是明显离谱的，不是精确判断的。**

## 输入要求

需要以下数据（由编排器从 Phase 1 + Gate 2 传递）：

- 当前股价、PE(TTM)、PB
- 近 5 年 PE(TTM) 每年高低点（用于计算中位数和波动范围）
- 行业平均 PE（如有，否则只使用历史 PE 判断）
- 近 5 年 ROE（来自 quality-screen）
- 近 1 年净利润（判断盈亏状态）
- 毛利率（辅助判断商业模式质量）

## 判定标准

### ABSURD — 价格离谱，不值得继续分析

满足**任一**条件即判定：

1. **PE 极端高估**: 当前 PE(TTM) > 近 5 年 PE 中位数 × 1.8（即高出 80%）
2. **高 PE + 低 ROE 组合**: PE(TTM) > 50 且近 5 年平均 ROE < 15%
3. **PB 极端**: PB > 10（资产定价完全脱离账面价值，通常意味着投机性泡沫）
4. **无盈利**: 近 1 年净利润为负，且近 3 年无稳定盈利记录（不能判断为周期性底部）
5. **PE 为零或负**: 无法计算 PE 且无合理替代估值方法

边界情况处理：
- 周期性行业（钢铁/化工/航运）当前 PE 极高可能是因为周期底部，检查近 5 年平均净利润是否为正。如果是正且 PB < 2，不判定 ABSURD。
- 金融行业（银行/保险/券商）PB 阈值放宽至 3（而非 10），因为金融企业 PB > 3 通常已严重高估。

### EXPENSIVE — 偏贵但可以继续分析

满足**任一**条件且不触发 ABSURD：

1. **PE 偏高**: 当前 PE(TTM) 在近 5 年 PE 中位数的 1.3–1.8 倍之间
2. **PE 远超行业**: 当前 PE(TTM) > 行业平均 PE × 2.0（且行业 PE 数据可靠）
3. **PB 偏高**: 5 < PB ≤ 10（非金融行业）

### REASONABLE — 价格在合理范围

不满足以上任何 ABSURD 或 EXPENSIVE 条件：

1. 当前 PE(TTM) ≤ 近 5 年 PE 中位数 × 1.3
2. 且不触发任何 EXPENSIVE 条件

## 输出格式

向编排器返回结构化判定结果：

```
判定: REASONABLE / EXPENSIVE / ABSURD

关键数据:
- 当前 PE(TTM): XX.X
- 近 5 年 PE 中位数: XX.X (范围: XX-XX)
- 当前 PB: X.X
- 近 5 年平均 ROE: XX%
- 行业平均 PE: XX (如有)

判定依据:
[具体说明触发了哪条判定规则]

芒格视角:
[1-2 句话——以芒格的口吻评价当前价格水平]

价格观察建议: (仅 ABSURD 时输出)
- 值得再来分析的参考价格: ¥XX.XX (= 近 5 年 PE 中位数 × 近 1 年 EPS)
- 当前价 vs 参考价: 需要下跌 XX% 才值得看
```

## 注意事项

- 你给的是快速判断，不是精确估值——不要花时间在精细计算上
- 历史 PE 中位数取近 5 年每年 PE(TTM) 的中位数，不是日线中位数
- 行业 PE 数据来自 industry_data.py，如获取失败标注"行业数据不可用，仅使用历史 PE 判断"
- 对金融/周期行业使用特殊边界条件（见 ABSURD 边界情况处理）
- 判定为 ABSURD 时不代表公司不好——只代表当前价格不值得分析
- 判定为 EXPENSIVE 时允许继续——在深度分析报告中会标注风险
```

- [ ] **Step 2: Verify file is well-formed**

Read the file back and confirm:
- YAML frontmatter has `name` and `description`
- All edge cases enumerated with explicit rules
- Industry exceptions documented

- [ ] **Step 3: Commit**

```bash
git add skills/valuation-gate.md
git commit -m "feat: add valuation-gate skill for Gate 3"
```

---

### Task 3: Create `skills/rejection-report.md` — Unified Rejection System

**Files:**
- Create: `skills/rejection-report.md`

- [ ] **Step 1: Write the complete skill file**

```markdown
---
name: rejection-report
description: 芒格拒绝报告生成器 — 统一处理三种门禁拒绝（TOO-HARD/NOT-QUALITY/TOO-EXPENSIVE），产出芒格风格的有价值拒绝输出
---

# 芒格拒绝报告生成器

你是查理·芒格风格的拒绝报告撰写人。你的核心信念是：**拒绝分析一家公司不是失败——这是系统在做芒格本人会做的事。** 每一次拒绝都应该为用户提供独立的价值。

芒格说："我们取得好成绩，不是因为我们做了很多事，而是因为我们避开了很多愚蠢的事。"

## 输入要求

由编排器传递以下数据：

- `REJECTION_TYPE`: 拒绝类型 — `TOO-HARD` (Gate 1) / `RESTRICTED` (Gate 1) / `NOT-QUALITY` (Gate 2) / `TOO-EXPENSIVE` (Gate 3)
- `STOCK_NAME`: 公司名称
- `STOCK_CODE`: 股票代码
- `GATE_DATA`: 触发拒绝的 Gate 的完整输出（circle-of-competence 或 quality-screen 或 valuation-gate 的判定结果）
- `KNOWN_INFO`: 已知基础数据摘要（Phase 1 收集到的行情/财务关键指标）
- `ADDITIONAL_GATE_DATA`: (可选) 第二个 Gate 的数据（如 RESTRICTED 时 Gate 2 的 quality-screen 结果）

## 统一拒绝报告结构

所有拒绝类型遵循同一结构，但各类型填充的侧重点不同：

```
🚫 **芒格判定：不投**

> [根据不同拒绝类型的一句话芒格口吻结论]

---

### 拒绝依据

[命中 Gate 的详细判定，包括评分卡/指标卡]

### 📋 已知信息摘要

[纯数据展示——不评分、不推荐、不估值]
[当前股价/市值/PE/ROE/毛利率/行业等可用数据]

### 🧭 研究路线图 (仅 TOO-HARD / RESTRICTED)

如果你仍想自行研究这家公司，以下是你需要回答的核心问题：

1. [业务本质问题]
2. [行业前景问题]
3. [数据缺口问题]
4. [致命风险问题]

### 💰 价格观察 (仅 TOO-EXPENSIVE)

- 值得再来分析的参考价格: ¥XX.XX
- 当前价比参考价高: XX%
- 建议: 放入观察清单，设置价格提醒

---

> [一句相关的芒格语录]

⚠️ 以上分析不构成投资建议。本系统遵循查理·芒格的投资哲学——承认无知比假装知道更有价值。
```

## 各拒绝类型的输出要求

### 类型 1: TOO-HARD (Gate 1)

**一句话结论模板：**
"这家公司超出了我们的能力圈。芒格不会投——不是因为公司不好，而是因为我们没有能力判断它好不好。"

**拒绝依据：** 展示 circle-of-competence 的输出——黑名单命中项 + 信息质量评分卡（4 维度得分表）。

**研究路线图：** 必须包含以下 4 个问题（基于公司具体情况定制）：

1. **业务本质**: 这个生意到底靠什么赚钱？能用一句话说清楚吗？如果一句话说不清楚，你很可能没有真正理解它。
2. **行业前景**: 这个行业 10 年后还存在吗？竞争格局会变成什么样？如果 10 年后的图景你画不出来，这就是一个"太难"的信号。
3. **数据缺口**: 如果能拿到更多数据，什么数据对你的判断最重要？这些数据你能拿到吗？如果拿不到，你就是在黑暗中开枪。
4. **致命风险**: 这家公司最可能被什么杀死？（技术颠覆？监管打击？关键人物离开？财务造假？）你能排除这些可能性吗？

### 类型 2: RESTRICTED (Gate 1)

**一句话结论模板：**
"我们对这家公司的理解受到[具体限制]的限制。在有更多可靠信息之前，芒格不会下注。"

**拒绝依据：** 展示 circle-of-competence 信息质量评分卡 + Gate 2 质量筛选结果（如有）。

**研究路线图：** 与 TOO-HARD 相同格式，但更聚焦于信息缺口而非能力圈边界。

**与 TOO-HARD 的区别：** RESTRICTED 的语气是"信息不够，但方向可行"；TOO-HARD 的语气是"这超出了我们的能力边界"。

### 类型 3: NOT-QUALITY (Gate 2)

**一句话结论模板：**
"这家公司的财务质量达不到芒格的一流公司标准。[最差指标]是致命的问题。"

**拒绝依据：** 展示 quality-screen 的 7 指标得分卡，高亮 FAIL 项。

**不展示研究路线图**——NOT-QUALITY 不需要更多研究，结论已经明确。

### 类型 4: TOO-EXPENSIVE (Gate 3)

**一句话结论模板：**
"公司也许不错，但当前价格已经完全脱离了地心引力。芒格不会在任何接近当前价格的价位考虑它。"

**拒绝依据：** 展示 valuation-gate 的判定——当前 PE vs 5 年中位数 vs 行业均值。

**价格观察：**
- 参考价格 = 近 5 年 PE 中位数 × 近 1 年 EPS
- 当前价 vs 参考价的差距百分比
- 明确说明："这不是目标价——这只是一个值得回头来看的价位。"

## 芒格语录库

根据拒绝类型选用一句最贴切的：

| 类型 | 推荐语录 |
|------|---------|
| TOO-HARD | "我们有三个篮子：投、不投、太难。大部分东西都进了'太难'那个篮子。" |
| RESTRICTED | "承认无知是智慧的开始。" |
| NOT-QUALITY | "以合理价格买伟大公司，比以便宜价格买烂公司好得多。" |
| TOO-EXPENSIVE | "投资的第一条规则是不要亏钱。第二条规则是不要忘记第一条。" |
| 通用 | "我们没有特别的优势去分析每一个行业、每一家公司。我们只在我们有优势的地方下注。" |

## 注意事项

- 拒绝报告的语气是**肯定而非抱歉**——"芒格不会投这个"而非"系统无法分析这个"
- 已知信息摘要只展示数据，**绝对不**附带任何评分、估值、推荐或暗示
- 研究路线图的问题必须针对具体公司定制，不是套话模板
- 所有拒绝报告底部必须包含免责声明
- 拒绝报告不生成 HTML 文件——在对话中直接以 markdown 形式展示
```

- [ ] **Step 2: Verify file is well-formed**

Read the file back and confirm all sections are complete with no placeholders.

- [ ] **Step 3: Commit**

```bash
git add skills/rejection-report.md
git commit -m "feat: add rejection-report skill for unified rejection output"
```

---

### Task 4: Modify `skills/quality-screen.md` — Gate 2 Adaptation

**Files:**
- Modify: `skills/quality-screen.md`

**Changes:** Three minor adjustments to adapt from being the sole gate to being Gate 2 of 3.

- [ ] **Step 1: Update the role description**

Read `skills/quality-screen.md` lines 6-8. Replace the role paragraph:

```markdown
你是查理·芒格风格的量化质量分析师。你的信条是："买好公司的第一步是排除烂公司"。你使用 7 条简单但有效的量化标准，像筛子一样淘汰不合格的公司。
```

Replace with:

```markdown
你是查理·芒格风格的量化质量分析师。你的信条是："买好公司的第一步是排除烂公司"。你使用 7 条简单但有效的量化标准，像筛子一样淘汰不合格的公司。

**你在三层门禁中的位置：Gate 2（能力圈审查 → 你在这里 → 估值合理性）**。你接收经过 Gate 1（能力圈）筛选后的标的。如果你的判定是 FAIL，系统将进入拒绝路径。如果你判定 PASS 或 CAUTION，标的将进入 Gate 3（估值门禁）。
```

- [ ] **Step 2: Add context to the input requirements section**

After line 12 (`- 近 5 年毛利率（每年）`), add:

```markdown
- Gate 1 能力圈判定结果（IN-CIRCLE 或 RESTRICTED）及评分（由编排器传递）
```

- [ ] **Step 3: Adjust the FAIL output note**

After line 101 (the "芒格视角" section), add a note:

```markdown
## Gate 2 角色说明

本 skill 是三层门禁系统的第二道。如果判定为 FAIL：
- 编排器将调用 `rejection-report` skill 产出统一格式的质量拒绝报告
- 拒绝报告将包含你的 7 项指标得分卡和芒格视角判断
- 如果标的同时带有 Gate 1 的 RESTRICTED 标记，拒绝报告将合并两个 Gate 的判断

如果判定为 PASS 或 CAUTION，标的将继续进入 Gate 3（估值门禁）。
```

- [ ] **Step 4: Verify the edits**

Read the full file and confirm:
- No existing functionality is broken
- New sections integrate cleanly with existing content
- Gate 2 positioning is clear

- [ ] **Step 5: Commit**

```bash
git add skills/quality-screen.md
git commit -m "refactor: adapt quality-screen to Gate 2 role in three-gate system"
```

---

### Task 5: Modify `skills/munger-orchestrator.md` — Full Orchestrator Refactor

**Files:**
- Modify: `skills/munger-orchestrator.md`

**Changes:** Insert Phase 1.5 (Gate 1), restructure Phase 2 (Gate 2 matrix logic), insert Phase 2.5 (Gate 3), add comprehensive rejection paths. This is a full replacement of the workflow section — everything from the old "## 5 阶段分析工作流" header through the end of the file.

- [ ] **Step 1: Replace the entire workflow section through end of file**

Read `skills/munger-orchestrator.md`. The first 41 lines (frontmatter, role, two modes) remain untouched. Everything from line 42 (`## 5 阶段分析工作流`) to the end of the file is replaced with the new content below.

Replace (starting from `## 5 阶段分析工作流` through end of file):

```markdown
## 5 阶段分析工作流

### Phase 0: 意图识别

确认：
- 分析对象是行业还是个股？
- 获取股票代码（如用户只给名称，先调 search）
- 告知用户即将开始的流程概览

```
🔍 **开始分析 <股票名称> (<股票代码>)**

我将按照查理芒格的分析框架，分以下步骤进行：
1. 📡 收集数据（行情+财务+估值+管理层+行业）
2. 🔢 质量筛选（7 指标去劣）
3. 🧠 四路分析（护城河 + 安全边际 + 管理层 + 逆向验证）
4. 🌍 全球龙头对标
5. 📊 生成投资报告

预计需要 3-5 分钟...
```

### Phase 1: 数据收集（并行）

调用 Bash 并行执行 5 路数据收集：

```bash
# A股核心数据（3路）
python tools/ashare_data.py quote <code> --json
python tools/ashare_data.py financials <code> --json --period 年报
python tools/ashare_data.py valuation <code> --json

# 管理层/股东数据
python tools/personnel_data.py full <code> --json

# 行业数据
python tools/industry_data.py <行业名称> --json
```

注意：行业名称需要从公司的业务描述中推断（如 600519 → 白酒），或者先用 WebSearch 快速确认公司所属行业。

然后调用 `financial-query` Skill 对关键数据进行交叉验证。

**进度提示**：告知用户数据获取状态。

**异常处理**：
- 某个数据源失败 → 标注 missing，继续流程
- 全部失败 → 告知用户，建议检查股票代码或网络

### Phase 2: 质量筛选（串行 — 把关第一步）

调用 `quality-screen` Skill，将 Phase 1 获取的数据传递给该 Skill 进行分析。

**分支处理**：
- ✅ PASS → 继续 Phase 3
- ⚠️ CAUTION → 继续 Phase 3，但提醒用户风险
- ❌ FAIL → **终止流程**

如果 FAIL:
```
🚫 **质量筛选未通过**

<股票名称> 在 [具体不通过的指标] 方面不符合芒格的一流公司标准。

按照芒格的原则："我们宁愿错过十个好机会，也不在一个烂机会上浪费时间。"

如果你仍然想深入了解这家公司，我可以继续分析，但请知悉：这家公司不符合基本质量门槛。
```
```

With:

```markdown
## 工作流总览：5 阶段 + 3 门禁

```
Phase 0: 意图识别
   ↓
Phase 1: 数据收集（5 路并行）
   ↓
Phase 1.5: Gate 1 — 能力圈审查 ← NEW
   ├── TOO-HARD → 拒绝路径 → 终止
   ├── RESTRICTED → 标记，继续 Gate 2 → 拒绝路径
   └── IN-CIRCLE → 继续
   ↓
Phase 2: Gate 2 — 质量筛选
   ├── FAIL (+ IN-CIRCLE) → 拒绝路径 → 终止
   ├── FAIL (+ RESTRICTED) → 拒绝路径 → 终止
   ├── PASS/CAUTION (+ RESTRICTED) → 拒绝路径（受限报告）→ 终止
   └── PASS/CAUTION (+ IN-CIRCLE) → 继续
   ↓
Phase 2.5: Gate 3 — 估值门禁 ← NEW
   ├── ABSURD → 拒绝路径 → 终止
   ├── EXPENSIVE → 继续（带警告标记）
   └── REASONABLE → 继续
   ↓
Phase 3: 四路并行分析（护城河+安全边际+管理层+逆向风险）
   ↓
Phase 4: 全球龙头对标（按需触发）
   ↓
Phase 5: 综合评分 + HTML 报告生成
```

**目标：60-80% 的分析请求在 1 分钟内完成拒绝。仅 20-40% 的标的进入 Phase 3-5 深度分析。**

---

### Phase 0: 意图识别

确认：
- 分析对象是行业还是个股？
- 获取股票代码（如用户只给名称，先调 search）
- 告知用户即将开始的流程概览

```
🔍 **开始分析 <股票名称> (<股票代码>)**

我将按照查理芒格的分析框架进行：
1. 📡 收集数据
2. 🎯 能力圈审查 → 质量筛选 → 估值合理性判断
3. 🧠 深度分析（仅通过三道门禁的标的）
4. 📊 生成报告

大多数标的会在第 2 步被拒绝——这是芒格会做的事。
```

### Phase 1: 数据收集（并行）

调用 Bash 并行执行 5 路数据收集：

```bash
# A股核心数据（3路）
python tools/ashare_data.py quote <code> --json
python tools/ashare_data.py financials <code> --json --period 年报
python tools/ashare_data.py valuation <code> --json

# 管理层/股东数据
python tools/personnel_data.py full <code> --json

# 行业数据
python tools/industry_data.py <行业名称> --json
```

注意：行业名称需要从公司的业务描述中推断（如 600519 → 白酒），或者先用 WebSearch 快速确认公司所属行业。

然后调用 `financial-query` Skill 对关键数据进行交叉验证。

**进度提示**：告知用户数据获取状态。

**异常处理**：
- 某个数据源失败 → 标注 missing，继续流程
- 全部失败 → 告知用户，建议检查股票代码或网络

---

### Phase 1.5: Gate 1 — 能力圈审查 ← NEW

这是系统最重要的决策点。在数据收集完成后，首先回答芒格的第一问：**"我懂这个生意吗？"**

#### Step 1.5a: 调用能力圈 Skill

调用 `circle-of-competence` Skill，传递：
- Phase 1 全部数据收集结果
- 行业分类（从主营业务描述推断或 WebSearch 确认）
- 上市时间、审计信息
- 数据收集完整性状态

#### Step 1.5b: 根据判定分支

**情况 A: TOO-HARD — 直接拒绝**

```
🚫 **能力圈审查: TOO-HARD**

<股票名称> 超出了我们的分析能力范围。

[展示 circle-of-competence 的判定依据]

正在生成拒绝报告...
```

调用 `rejection-report` Skill，传递：
- `REJECTION_TYPE`: `TOO-HARD`
- `STOCK_NAME`, `STOCK_CODE`
- `GATE_DATA`: circle-of-competence 的完整输出
- `KNOWN_INFO`: Phase 1 数据摘要

展示拒绝报告。**流程终止。**

**情况 B: RESTRICTED — 受限分析**

```
⚠️ **能力圈审查: RESTRICTED**

<股票名称> 在某些关键维度上信息不足，我们的分析将受到限制。

[展示受限的维度]

先完成质量筛查以收集更多数据，然后将产出受限报告。
```

设置内部标记 `GATE1_VERDICT = RESTRICTED`。
**继续执行 Gate 2**（用于收集数据丰富拒绝报告），但无论 Gate 2 结果如何，最终都走拒绝路径。

**情况 C: IN-CIRCLE — 通过**

```
✅ **能力圈审查: 通过** (可分析性评分: X.X/10)

这家公司在我们的能力圈范围内。继续质量筛选...
```

设置内部标记 `GATE1_VERDICT = IN-CIRCLE`。
继续执行 Gate 2。

---

### Phase 2: Gate 2 — 质量筛选

调用 `quality-screen` Skill，传递 Phase 1 数据 + Gate 1 判定结果。

#### 矩阵判断逻辑

结合 Gate 1 和 Gate 2 的判定结果，使用以下矩阵：

| | Gate 1 = IN-CIRCLE | Gate 1 = RESTRICTED |
|---|---|---|
| **Gate 2 = PASS** | ✅ → Gate 3 | ⚠️ 受限报告 |
| **Gate 2 = CAUTION** | ✅ → Gate 3 (标注风险) | ⚠️ 受限报告 |
| **Gate 2 = FAIL** | 🚫 质量拒绝 | 🚫 质量拒绝 (含能力圈警告) |

#### 各分支处理

**分支 1: IN-CIRCLE + PASS/CAUTION → 继续 Gate 3**

```
✅ **质量筛选: PASS/CAUTION** (总分: X.X/10)

继续估值合理性判断...
```

**分支 2: IN-CIRCLE + FAIL → 质量拒绝**

```
🚫 **质量筛选: FAIL** (总分: X.X/10)

<股票名称> 不符合芒格的一流公司标准。

正在生成拒绝报告...
```

调用 `rejection-report` Skill：
- `REJECTION_TYPE`: `NOT-QUALITY`
- `GATE_DATA`: quality-screen 完整输出
- `KNOWN_INFO`: Phase 1 数据摘要

展示拒绝报告。**流程终止。** 不提供"继续分析"的选项——质量 FAIL 的公司不值得花时间。

**分支 3: RESTRICTED + 任何 Gate 2 结果 → 受限报告**

```
⚠️ **受限分析**

<股票名称> 的分析受到信息限制。以下是我们能提供的全部内容...
```

调用 `rejection-report` Skill：
- `REJECTION_TYPE`: `RESTRICTED`
- `GATE_DATA`: circle-of-competence 输出
- `ADDITIONAL_GATE_DATA`: quality-screen 输出
- `KNOWN_INFO`: Phase 1 数据摘要

展示受限报告。**流程终止。**

---

### Phase 2.5: Gate 3 — 估值门禁 ← NEW

**触发条件：** 仅当 Gate 1 = IN-CIRCLE 且 Gate 2 = PASS 或 CAUTION。

从 Phase 1 数据中提取：
- 当前 PE(TTM)、PB
- 近 5 年 PE 中位数（valuation 数据）
- 行业平均 PE（如有）
- quality-screen 的 ROE 和毛利率数据

调用 `valuation-gate` Skill，传递以上数据。

#### 分支处理

**情况 A: ABSURD — 估值离谱**

```
💰 **估值门禁: 价格离谱**

<股票名称> 当前价格完全脱离了合理范围。

正在生成拒绝报告...
```

调用 `rejection-report` Skill：
- `REJECTION_TYPE`: `TOO-EXPENSIVE`
- `GATE_DATA`: valuation-gate 完整输出
- `KNOWN_INFO`: Phase 1 数据摘要

展示拒绝报告。**流程终止。**

**情况 B: EXPENSIVE — 偏贵但允许继续**

```
⚠️ **估值门禁: 价格偏高**

当前 PE 显著高于历史中位数。继续分析，但将在报告中标注估值风险。
```

设置标记 `EXPENSIVE_WARNING = true`。
继续 Phase 3。

**情况 C: REASONABLE — 价格合理**

```
✅ **估值门禁: 价格合理**

当前估值在历史可比范围内。继续深度分析...
```

继续 Phase 3。

---

### Phase 3: 并行分析

**触发条件：** 仅当三道门禁全部通过（Gate 1 = IN-CIRCLE, Gate 2 = PASS/CAUTION, Gate 3 = REASONABLE/EXPENSIVE）。

**同时**调用 4 个分析 Skill：
1. `moat-analysis` — 护城河分析
2. `safety-margin` — 安全边际评估
3. `management-check` — 管理层审查
4. `inversion-test` — 逆向风险验证

将 Phase 1-2 的数据和结论传递给这 4 个 Skill。moat-analysis 可使用 industry_data 的行业均值做对标。

如果 `EXPENSIVE_WARNING = true`，额外传递提示："当前估值偏高，请在安全边际评估中重点考虑估值风险。"

### Phase 4: 全球对标（按需触发）

触发条件（与当前版本相同）：
- 通过 WebSearch 或常识判断该行业存在全球可比龙头
- 用户明确要求全球对标
- 典型可对标行业：消费（可口可乐）、科技（台积电）、汽车（丰田）、医药（辉瑞）、制造（卡特彼勒）
- 通常不触发：中国独有行业（白酒、中药）、强政策管制行业（军工）

**触发时：**
1. 通过 WebSearch + 常识确定 1-3 个全球龙头股票代码
2. 调用 `global_data.py` 获取对标数据
3. 将 A 股数据 + 对标数据传递给 `global-benchmark` Skill

**不触发时：**
- 跳过该 Phase
- 在 Phase 5 综合评分中 global-benchmark 权重归零，其余 5 维度按比例重分配（÷0.9）

### Phase 5: 报告生成

#### Step 5a: 计算综合评分

基于各分析 Skill 的输出计算综合评分：

| 维度 | 权重 | 得分来源 |
|------|------|---------|
| 质量筛选 | 20% | quality-screen |
| 护城河宽度 | 25% | moat-analysis |
| 安全边际 | 20% | safety-margin |
| 管理层质量 | 15% | management-check |
| 逆向风险 | 10% | inversion-test |
| 全球对标 | 10% | global-benchmark |

**特殊情况:** global-benchmark 返回"不适用"时 → 权重归零，其余 5 维度按 ÷0.9 重分配权重。

**评分计算:** 综合评分 = Σ(维度得分 × 权重)

评级映射：
- 8-10: 强烈推荐
- 6-8: 可以买入
- 4-6: 继续观察
- < 4: 回避

**Gate 3 标记处理:** 如果 `EXPENSIVE_WARNING = true`，在综合评分中不额外扣分，但在报告的一句话结论中明确提及"当前估值偏高"。

#### Step 5b: 汇总所有输出

收集以下内容并组织为报告生成器需要的格式：

1. **基础信息**: 从 Phase 1 的数据中提取：公司名称、代码、当前股价、总市值、报告日期
2. **综合评分**: 按上述公式计算
3. **一句话结论**: 基于所有分析结果，撰写芒格风格的总结（2-3 句话）
4. **核心优势/风险**: 从各分析 Skill 中提取
5. **分析模块 HTML**: 将每个分析 Skill 的输出格式化为 HTML 片段
6. **图表数据**: 从财务数据中提取 5 年趋势数据（营收/净利润/ROE 数组）
7. **雷达图数据**: 各维度得分
8. **买入价格 HTML**: 从 safety-margin 输出中提取三档买入价格
9. **管理层 HTML**: management-check 输出
10. **逆向风险 HTML**: inversion-test 输出
11. **全球对标 HTML**: global-benchmark 输出（不适用时传占位 HTML）

#### Step 5c: 调用报告生成器

调用 `report-generator` Skill，将汇总数据传递给该 Skill 生成 HTML 报告。报告写入 `reports/<STOCK_CODE>-<YYYY-MM-DD>.html`。

---

## 异常处理总则

| 场景 | 处理 |
|------|------|
| 工具脚本执行失败 | 重试 1 次，仍失败则标记 missing |
| 数据全部不可用 | 告知用户并终止（这本身触发了 Gate 1 TOO-HARD） |
| 用户中途改变意图 | 优雅切换模式，保存已有分析结果 |
| Gate 1 TOO-HARD | 产出拒绝报告（含研究路线图），终止 |
| Gate 2 FAIL (+ IN-CIRCLE) | 产出质量拒绝报告，终止 |
| Gate 2 FAIL (+ RESTRICTED) | 产出拒绝报告（含 Gate 1+2 依据），终止 |
| RESTRICTED + Gate 2 PASS/CAUTION | 产出受限报告（含已知信息卡 + 研究路线图），终止 |
| Gate 3 ABSURD | 产出估值拒绝报告（含观察清单建议），终止 |
| 分析 Skill 返回内容过少 | 标注"数据有限，分析受限" |

## 拒绝路径总结

| 路径 | Gate 1 | Gate 2 | Gate 3 | 拒绝类型 | 产出 |
|------|--------|--------|--------|---------|------|
| A | TOO-HARD | — | — | TOO-HARD | 拒绝 + 研究路线图 |
| B | RESTRICTED | FAIL | — | RESTRICTED | 拒绝 + 已知信息卡 + 路线图 |
| C | RESTRICTED | PASS/CAUTION | — | RESTRICTED | 受限报告 + 已知信息卡 + 路线图 |
| D | IN-CIRCLE | FAIL | — | NOT-QUALITY | 质量拒绝 |
| E | IN-CIRCLE | PASS/CAUTION | ABSURD | TOO-EXPENSIVE | 估值拒绝 + 观察清单 |
| F | IN-CIRCLE | PASS/CAUTION | REASONABLE/EXPENSIVE | — | 完整 HTML 报告 |

## 交互规范

1. **进度可见**: 每个 Phase 开始时告知用户正在做什么
2. **数据透明**: 所有结论引用具体数据支撑
3. **不确定性诚实**: 不知道的事就说不知道
4. **芒格语调**: 分析结论遵循芒格的表达风格——不模棱两可，不迎合用户
5. **拒绝是成功**: 拒绝一家公司时用肯定的语气——"芒格不会投这个"，而非"系统无法分析"
6. **最终输出**: 完整分析路径 → HTML 报告；拒绝路径 → Markdown 拒绝报告（对话中展示）
```

- [ ] **Step 2: Verify the refactored orchestrator is coherent**

Read the full file and confirm:
- Phase numbering is consistent (0, 1, 1.5, 2, 2.5, 3, 4, 5)
- All 6 rejection paths (A-F) are described with clear triggers
- Phase 3-5 content remains intact
- The matrix logic table is unambiguous

- [ ] **Step 3: Commit**

```bash
git add skills/munger-orchestrator.md
git commit -m "refactor: add three-gate architecture to orchestrator (Gates 1, 2, 3)"
```

---

### Task 6: End-to-End Validation

**Files:** None (validation only)

- [ ] **Step 1: Verify all new skill files exist and are well-formed**

```bash
ls -la skills/circle-of-competence.md skills/valuation-gate.md skills/rejection-report.md
```

For each file, check:
- YAML frontmatter has `name` and `description` fields
- No `TBD`, `TODO`, or incomplete placeholders
- Markdown tables are properly formatted

- [ ] **Step 2: Verify modified files are consistent**

```bash
grep -n "Gate" skills/quality-screen.md
grep -n "Phase 1.5\|Phase 2.5\|Gate 1\|Gate 2\|Gate 3\|拒绝路径" skills/munger-orchestrator.md
```

Confirm:
- quality-screen.md references its Gate 2 role
- orchestrator has all three gates and all six rejection paths (A-F)
- Rejection path summary table lists 6 paths

- [ ] **Step 3: Verify the complete file inventory matches the spec**

Expected state:
- **New files (3):** `skills/circle-of-competence.md`, `skills/valuation-gate.md`, `skills/rejection-report.md`
  - (Spec listed 4; `too-hard-report.md` was merged into `rejection-report.md` per spec self-review)
- **Modified files (2):** `skills/munger-orchestrator.md`, `skills/quality-screen.md`
- **Unchanged files (8):** `skills/moat-analysis.md`, `skills/safety-margin.md`, `skills/management-check.md`, `skills/inversion-test.md`, `skills/global-benchmark.md`, `skills/report-generator.md`, `skills/a-share-data.md`, `skills/financial-query.md`
- **Unchanged tools (4):** `tools/ashare_data.py`, `tools/personnel_data.py`, `tools/industry_data.py`, `tools/global_data.py`

```bash
git status
```

- [ ] **Step 4: Dry-run a rejection scenario**

Mentally walk through: User says "分析一下 600519" (Kweichow Moutai —白酒行业, strong financials).

Expected path:
- Phase 1: Data collected successfully
- Gate 1: 白酒 → no blacklist hit, 财务数据完整 → 2.5, 业务可理解 → 2.5 (卖白酒的), 信息真实性 → 2.5 (国企龙头), 行业可预测 → 2.5 (需求稳定) → Total ~10 → IN-CIRCLE
- Gate 2: Strong ROE, margins, cash flow → likely PASS
- Gate 3: PE vs 5y median → check → likely REASONABLE or EXPENSIVE
- → **完整分析路径** (correct — Moutai is a Munger-style stock)

Mentally walk through: User says "分析一下某个军工股".

Expected path:
- Phase 1: Data collected
- Gate 1: 军工 → blacklist #1 hit → 如果仅 1 项，继续信息质量评分 → 行业可预测性: 政策博弈，难以预测 → 0.5 → 数据红线触发 → max RESTRICTED
- → **拒绝路径 B or C** (correct — military is outside circle of competence)

Mentally walk through: User says "分析一下某个 PE=200 的 AI 概念股".

Expected path:
- Phase 1: Data collected
- Gate 1: AI 芯片可能命中 blacklist #2（技术迭代过快），或至少信息质量评分受影响
- If passes Gate 1: Gate 2 quality screening
- If passes Gate 2: Gate 3 → PE=200 vs 5y median likely > 1.8x → ABSURD
- → **拒绝路径 E** (correct — absurd valuation)

- [ ] **Step 5: Final commit if any validation fixes were needed**

```bash
git status
git diff
```
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final validation of three-gate architecture"
```

---

*Plan written: 2026-07-10*
*Spec reference: docs/superpowers/specs/2026-07-10-three-gate-rejection-architecture.md*
