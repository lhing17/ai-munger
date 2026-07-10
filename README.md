# AI Munger — 查理芒格投资分析 Agent

以**查理·芒格**投资哲学为核心的 AI 投资分析助手。通过多轮对话，Agent 驱动数据工具和分析技能，**大部分标的在 1 分钟内被拒绝**——仅 20-40% 通过全部三道门禁，进入完整的深度分析并生成交互式 HTML 报告。

## 哲学基础

> "我们有三个篮子：投、不投、太难。大部分东西都进了'太难'那个篮子。" — 查理·芒格

本系统认真对待"太难"这个篮子。拒绝不是失败——拒绝是系统做了芒格会做的事。

对于通过三道门禁的少数标的，系统以芒格的分析框架进行深度评估。但我们坦承：[一个 AI 系统不可能真正做到芒格式分析](docs/munger-philosophy-fidelity-analysis.md)——芒格的判断是整体性的、依赖数十年跨学科积累的、无法分解为加权评分公式的。这个系统在**精神气质**上模仿芒格，但在**认知方法**上是用量化筛选 + LLM 定性判断的混合体。

## 功能

- 💬 **自由问答** — "茅台 PE 多少？""搜索一下比亚迪"
- 🚫 **快速拒绝** — 大多数分析请求在 60 秒内被拒绝，产出有价值的拒绝报告（含已知信息卡 + 研究路线图）
- 📊 **深度分析** — 仅对通过三道门禁的标的启动完整分析流程
- 📄 **HTML 报告** — 含雷达图、趋势图、买入价格区间、可折叠详情面板
- 🇨🇳 **A 股优先** — 腾讯行情 + 东方财富数据，支持与全球龙头对标

## 快速开始

```bash
# 1. 启动 Claude Code
cd D:/HL/ai-munger
claude

# 2. 自由问答
> 茅台现在 PE 多少？

# 3. 深度分析（大部分会被拒绝）
> 分析一下 600519
> 深度研究一下招商银行
```

## 架构：5 阶段 + 3 门禁

```
用户输入 "分析 X 公司"
    ↓
Phase 0: 意图识别
    ↓
Phase 1: 数据收集（5 路并行）
    ↓
Phase 1.5: Gate 1 — 能力圈审查 ← 行业黑名单 + 信息质量评分
    ├── TOO-HARD → 拒绝 + 研究路线图
    ├── RESTRICTED → 受限报告
    └── IN-CIRCLE → 继续
    ↓
Phase 2: Gate 2 — 质量筛选 ← 7 指标去劣
    ├── FAIL → 质量拒绝
    └── PASS/CAUTION → 继续
    ↓
Phase 2.5: Gate 3 — 估值门禁 ← PE/中位数快速判断
    ├── ABSURD → 估值拒绝 + 观察清单
    ├── EXPENSIVE → 继续（带警告标记）
    └── REASONABLE → 继续
    ↓
Phase 3: 四路并行分析 ← 护城河 + 安全边际 + 管理层 + 逆向风险
    ↓
Phase 4: 全球龙头对标（按需触发）
    ↓
Phase 5: 综合评分 + HTML 报告生成
```

**目标：60-80% 的分析请求在 1 分钟内完成拒绝。仅 20-40% 的标的进入 Phase 3-5 深度分析。**

### 三层门禁

| Gate | Skill | 判定 | 拒绝输出 |
|------|-------|------|---------|
| Gate 1 | `circle-of-competence` | IN-CIRCLE / RESTRICTED / TOO-HARD | 拒绝 + 研究路线图 |
| Gate 2 | `quality-screen` | PASS / CAUTION / FAIL | 7 指标得分卡 |
| Gate 3 | `valuation-gate` | REASONABLE / EXPENSIVE / ABSURD | 估值拒绝 + 观察清单 |

### 6 条拒绝路径

| 路径 | Gate 1 | Gate 2 | Gate 3 | 拒绝类型 | 产出 |
|------|--------|--------|--------|---------|------|
| A | TOO-HARD | — | — | TOO-HARD | 拒绝 + 研究路线图 |
| B | RESTRICTED | FAIL | — | RESTRICTED_WITH_FAIL | 双重拒绝 |
| C | RESTRICTED | PASS/CAUTION | — | RESTRICTED | 受限报告 + 路线图 |
| D | IN-CIRCLE | FAIL | — | NOT-QUALITY | 质量拒绝 |
| E | IN-CIRCLE | PASS/CAUTION | ABSURD | TOO-EXPENSIVE | 估值拒绝 + 观察清单 |
| F | IN-CIRCLE | PASS/CAUTION | REASONABLE | — | 完整 HTML 报告 |

## 核心 Skills

### 门禁层

| Skill | 用途 | 说明 |
|-------|------|------|
| `circle-of-competence` | 🎯 Gate 1: 能力圈审查 | 行业黑名单（4 类）+ 信息质量评分（4 维度，满分 10） |
| `quality-screen` | 🔢 Gate 2: 质量筛选 | 7 条量化指标去劣（ROE/盈利/负债/现金流/毛利率/应收/商誉） |
| `valuation-gate` | 💰 Gate 3: 估值门禁 | PE vs 5 年中位数，排除明显离谱的定价 |
| `rejection-report` | 🚫 统一拒绝报告 | 4 种拒绝类型（TOO-HARD/RESTRICTED/NOT-QUALITY/TOO-EXPENSIVE）的统一输出 |

### 分析层（Phase 3-5，仅通过三道门禁的标的）

| Skill | 用途 | 芒格原则 |
|-------|------|---------|
| `moat-analysis` | 🏰 护城河分析 | "伟大的公司都有宽阔的护城河" — 5 维度评估 |
| `safety-margin` | 🛡️ 安全边际评估 | "以合理价格买伟大公司" — DCF + PE + 清算价值 |
| `management-check` | 👤 管理层审查 | "我们只投资我们信任的管理层" — 5 维度信任评分 |
| `inversion-test` | 🔍 逆向风险验证 | "告诉我我会死在哪里，我就永远不去那里" — 职业空头视角 |
| `global-benchmark` | 🌍 全球龙头对标 | 与全球可比龙头的估值与竞争力对比 |

### 编排与报告

| Skill | 用途 |
|-------|------|
| `munger-orchestrator` | 🎯 总编排 — 管理 5 阶段 + 3 门禁工作流 |
| `report-generator` | 📄 生成交互式 HTML 报告 |

### 数据获取

| Skill | 用途 |
|-------|------|
| `a-share-data` | 📡 A 股行情/财务/估值/搜索 |
| `financial-query` | 📡 财务数据交叉验证 |

## 数据脚本

所有工具脚本位于 `tools/` 目录，零外部依赖：

```bash
# 实时行情
python tools/ashare_data.py quote 600519 --json

# 财务数据
python tools/ashare_data.py financials 600519 --json --period 年报

# 估值指标
python tools/ashare_data.py valuation 600519 --json

# 搜索股票
python tools/ashare_data.py search 茅台 --json

# 全球对标数据
python tools/global_data.py AAPL --json

# 管理层/股东数据
python tools/personnel_data.py full 600519 --json

# 行业数据
python tools/industry_data.py 白酒 --json
```

## 项目结构

```
ai-munger/
├── tools/                           # Python CLI 数据脚本（零外部依赖）
├── .claude/skills/                  # Claude Code Skills（每个技能一个目录 + SKILL.md）
│   ├── circle-of-competence/        # 🎯 Gate 1: 能力圈审查
│   │   └── SKILL.md
│   ├── quality-screen/              # 🔢 Gate 2: 质量筛选
│   │   └── SKILL.md
│   ├── valuation-gate/              # 💰 Gate 3: 估值门禁
│   │   └── SKILL.md
│   ├── rejection-report/            # 🚫 统一拒绝报告
│   │   └── SKILL.md
│   ├── munger-orchestrator/         # 🎯 编排器
│   │   └── SKILL.md
│   ├── moat-analysis/               # 🏰 护城河分析
│   │   └── SKILL.md
│   ├── safety-margin/               # 🛡️ 安全边际
│   │   └── SKILL.md
│   ├── management-check/            # 👤 管理层审查
│   │   └── SKILL.md
│   ├── inversion-test/              # 🔍 逆向风险验证
│   │   └── SKILL.md
│   ├── global-benchmark/            # 🌍 全球对标
│   │   └── SKILL.md
│   ├── report-generator/            # 📄 报告生成
│   │   └── SKILL.md
│   ├── a-share-data/                # 📡 A 股数据
│   │   └── SKILL.md
│   └── financial-query/             # 📡 财务验证
│       └── SKILL.md
├── templates/                       # HTML 报告模板
├── reports/                         # 生成的报告输出
├── docs/                            # 设计文档与分析
│   ├── munger-philosophy-fidelity-analysis.md  # 芒格哲学忠实度分析
│   └── superpowers/
│       ├── specs/                   # 设计规格
│       └── plans/                   # 实现计划
├── CLAUDE.md                        # 项目入口（Agent 指令）
└── README.md                        # 本文件
```

## 关键约束

1. **免责声明**: 所有报告必须内嵌免责声明
2. **数据来源标注**: 每个指标标注数据来源
3. **缺数据保守处理**: 缺数据时评分默认保守，宁错杀不滥分析
4. **不预测股价走势**: 只给估值区间，不给"目标价"
5. **芒格风格**: 简洁直接、逆向思维、承认无知
6. **拒绝是成功**: 拒绝一家公司不是系统失败——是系统做了芒格会做的事

## 已知局限

本项目坦承其根本局限——详见 [芒格哲学忠实度分析](docs/munger-philosophy-fidelity-analysis.md)：

- **芒格的判断是整体性的**，无法被分解为加权评分公式和线性工作流
- **LLM 的判断是模式匹配**，不是对商业因果链的深度理解
- **AI 没有恐惧、贪婪或认知偏差**需要克服——它模仿的是芒格的"输出"而非芒格的"过程"
- 系统是一个**在精神气质上模仿芒格、但在认知方法上背离芒格**的量化筛选工具

## 致谢

本项目深受 [ai-berkshire](https://github.com/xbtlin/ai-berkshire) 启发——一个将巴菲特、芒格、段永平、李录四位价值投资大师的方法论系统化应用于 AI Agent 的开源框架。

AI Munger 是对 ai-berkshire 的致敬与专注化实践：将镜头对准查理·芒格一人，围绕他独特的**逆向思维、能力圈、承认无知**哲学，构建一个以**快速拒绝**为核心行为的芒格式投资分析助手。

## 免责声明

⚠️ 本项目生成的报告由 AI 基于公开数据自动生成，**不构成投资建议**。所有分析基于查理·芒格投资哲学框架，仅供参考。投资有风险，入市需谨慎。

## License

MIT
