# AI Munger — 查理芒格投资分析 Agent

以查理·芒格投资哲学为核心的 AI 投资分析助手。用户通过多轮对话与 Agent 交互，Agent 驱动数据工具和分析技能，最终生成交互式 HTML 投资分析报告。

Inspired by [ai-berkshire](https://github.com/xbtlin/ai-berkshire) — 专注芒格一人的投资分析实践。

## 架构

5 层分层架构：工具层(Python CLI) → 数据层(Skills) → 分析层(Skills) → 编排层(Skill) → 报告层(HTML)

## 目录

```
ai-munger/
├── tools/                   # Python CLI 数据脚本（零外部依赖）
├── .claude/skills/          # Claude Code Skills（官方规范：每个技能一个目录 + SKILL.md）
│   ├── circle-of-competence/# 🎯 Gate 1: 能力圈审查
│   ├── quality-screen/      # 🔢 Gate 2: 质量筛选
│   ├── valuation-gate/      # 💰 Gate 3: 估值门禁
│   ├── rejection-report/    # 🚫 统一拒绝报告
│   ├── munger-orchestrator/ # 🎯 编排器
│   ├── moat-analysis/       # 🧠 护城河分析
│   ├── safety-margin/       # 🧠 安全边际
│   ├── management-check/    # 🧠 管理层审查
│   ├── inversion-test/      # 🧠 逆向风险
│   ├── global-benchmark/    # 🧠 全球对标
│   ├── report-generator/    # 📄 报告生成
│   ├── a-share-data/        # 📡 A 股数据
│   └── financial-query/     # 📡 财务验证
├── templates/               # HTML 报告模板
├── reports/                 # 生成的报告存档
└── CLAUDE.md                # 本文件
```

## 使用方式

### 快速问答
直接提问，Agent 将按需调用数据工具：
- "茅台现在 PE 多少？"
- "帮我搜一下比亚迪的股票代码"

### 深度分析
使用触发词启动完整分析流程：
- "分析一下 600519" / "帮我评估茅台"
- "深度研究一下招商银行"

深度分析流程：数据收集 → **能力圈审查(Gate 1)** → **质量筛选(Gate 2)** → **估值门禁(Gate 3)** → 四路并行分析（护城河+安全边际+管理层+逆向风险）→ 全球对标 → HTML 报告

大多数标的在门禁阶段被拒绝（60-80%）——这是芒格会做的事。

## 核心 Skills

### 门禁层（前置拒绝系统）

| Skill | 用途 | 触发条件 |
|-------|------|---------|
| `circle-of-competence` | 🎯 Gate 1: 能力圈审查 | Phase 1.5 — 行业黑名单 + 信息质量评分 |
| `quality-screen` | 🔢 Gate 2: 质量筛选 | Phase 2 — 7 指标去劣 |
| `valuation-gate` | 💰 Gate 3: 估值门禁 | Phase 2.5 — PE vs 历史中位数快速判断 |
| `rejection-report` | 🚫 统一拒绝报告 | 任何门禁触发拒绝时 |

### 分析层（Phase 3-5，仅通过三道门禁的标的）

| Skill | 用途 | 触发条件 |
|-------|------|---------|
| `moat-analysis` | 🏰 护城河分析 | 分析流程 Phase 3 — 5 维度评估 |
| `safety-margin` | 🛡️ 安全边际评估 | 分析流程 Phase 3 — DCF + PE + 清算价值 |
| `management-check` | 👤 管理层审查 | 分析流程 Phase 3 — 5 维度信任评分 |
| `inversion-test` | 🔍 逆向风险验证 | 分析流程 Phase 3 — 职业空头视角 |
| `global-benchmark` | 🌍 全球龙头对标 | 分析流程 Phase 4（按需触发） |
| `report-generator` | 📄 报告生成 | 分析流程 Phase 5 |

### 编排与数据

| Skill | 用途 | 触发条件 |
|-------|------|---------|
| `munger-orchestrator` | 🎯 总编排 | 用户启动深度分析时 |
| `a-share-data` | 📡 A 股数据获取 | 需要行情/财务/估值数据时 |
| `financial-query` | 📡 财务交叉验证 | 数据需要验证时 |

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

## 关键约束

1. **免责声明**: 所有报告必须内嵌免责声明
2. **数据来源标注**: 每个指标标注数据来源
3. **缺数据保守处理**: 缺数据时评分默认为保守
4. **不预测股价走势**: 只给估值区间，不给"目标价"
5. **芒格风格**: 简洁直接、逆向思维、承认无知
