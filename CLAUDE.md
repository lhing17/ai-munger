# AI Munger — 查理芒格投资分析 Agent

以查理·芒格投资哲学为核心的 AI 投资分析助手。用户通过多轮对话与 Agent 交互，Agent 驱动数据工具和分析技能，最终生成交互式 HTML 投资分析报告。

Inspired by [ai-berkshire](https://github.com/xbtlin/ai-berkshire) — 专注芒格一人的投资分析实践。

## 架构

5 层分层架构：工具层(Python CLI) → 数据层(Skills) → 分析层(Skills) → 编排层(Skill) → 报告层(HTML)

## 目录

```
ai-munger/
├── tools/           # Python CLI 数据脚本（零外部依赖）
├── skills/          # Claude Code Skills（技能文件）
├── templates/       # HTML 报告模板
├── reports/         # 生成的报告存档
└── CLAUDE.md        # 本文件
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

深度分析流程：数据收集 → 质量筛选 → 护城河分析 + 安全边际 → HTML 报告

## 核心 Skills

| Skill | 用途 | 触发条件 |
|-------|------|---------|
| `munger-orchestrator` | 🎯 总编排 | 用户启动深度分析时 |
| `a-share-data` | 📡 A 股数据获取 | 需要行情/财务/估值数据时 |
| `financial-query` | 📡 财务交叉验证 | 数据需要验证时 |
| `quality-screen` | 🧠 质量筛选 | 分析流程 Phase 2 |
| `moat-analysis` | 🧠 护城河分析 | 分析流程 Phase 3 |
| `safety-margin` | 🧠 安全边际评估 | 分析流程 Phase 3 |
| `report-generator` | 📄 报告生成 | 分析流程 Phase 5 |

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
```

## 关键约束

1. **免责声明**: 所有报告必须内嵌免责声明
2. **数据来源标注**: 每个指标标注数据来源
3. **缺数据保守处理**: 缺数据时评分默认为保守
4. **不预测股价走势**: 只给估值区间，不给"目标价"
5. **芒格风格**: 简洁直接、逆向思维、承认无知
