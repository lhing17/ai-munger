# AI Munger 第二批 — 补齐分析深度 设计文档

> 日期：2026-07-10 | 状态：设计阶段 | 版本：1.0
> 关联文档：[第一批设计](./2026-07-10-ai-munger-agent-design.md)

## 1. 目标

将分析 Skill 从 3 个扩至 6 个，使综合评分从 3/6 维度占位变为 6/6 完整覆盖。新增管理层审查、逆向思维验证、全球龙头对标三个分析维度，并配套新增 3 个工具脚本。

**核心效果：**
- 综合评分 6/6 维度全部有真实数据来源
- Phase 3 并行度从 2 路提升至 4 路
- Phase 4（全球对标）从未实现变为激活
- 补齐芒格"多元思维模型"体系中的管理层评估和逆向思维两块核心拼图

---

## 2. 文件清单

| # | 文件 | 操作 | 职责 | 预计行数 |
|---|------|------|------|---------|
| 1 | `tools/global_data.py` | 新建 | yfinance 全球股票数据 CLI | ~300 |
| 2 | `tools/personnel_data.py` | 新建 | 高管/股东/质押数据 CLI | ~250 |
| 3 | `tools/industry_data.py` | 新建 | 行业均值/排名 CLI | ~150 |
| 4 | `skills/management-check.md` | 新建 | 5 维度管理层审查 | ~150 |
| 5 | `skills/inversion-test.md` | 新建 | 5 类逆向风险验证 | ~130 |
| 6 | `skills/global-benchmark.md` | 新建 | 全球龙头对标分析 | ~120 |
| 7 | `skills/munger-orchestrator.md` | 修改 | Phase 1/3/4 + 评分表 | +30 |
| 8 | `templates/report-base.html` | 修改 | 3 个新 section 占位符 | +20 |
| 9 | `skills/report-generator.md` | 修改 | 3 个新变量映射 | +10 |
| 10 | `CLAUDE.md` | 修改 | Skills 和工具索引 | +15 |

---

## 3. 工具层设计

### 3.1 global_data.py

**依赖:** `yfinance`（pip install，唯一新增外部依赖）
**数据源:** Yahoo Finance API
**风格:** 与 ashare_data.py 一致（`--json` 输出、结构化错误）

**命令：**

```bash
python tools/global_data.py AAPL --json           # 单只完整数据
python tools/global_data.py AAPL MSFT GOOGL --json # 批量对标
python tools/global_data.py TSM --json --financials # 仅财务
```

**返回结构（单只）：**

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "quote": {
    "price": 245.80, "market_cap": 3750000000000,
    "pe_ttm": 35.2, "pb": 52.3,
    "52w_high": 260.10, "52w_low": 164.08
  },
  "financials": {
    "years": ["2021","2022","2023","2024","2025"],
    "revenue": [365800000000, ...],
    "net_income": [94700000000, ...],
    "roe": [1.47, 1.60, 1.62, 1.46, 1.72],
    "gross_margin": [43.3, 43.3, 44.1, 45.9, 46.2],
    "r_and_d_pct": [6.5, 6.8, 7.0, 7.6, 7.8],
    "fcf": [105000000000, ...]
  },
  "growth": {
    "revenue_cagr_3y": 0.7, "revenue_cagr_5y": 1.3,
    "eps_cagr_3y": 5.8, "eps_cagr_5y": 12.1
  },
  "dividend": { "yield": 0.004, "payout_ratio": 0.15 }
}
```

### 3.2 personnel_data.py

**依赖:** 零外部依赖（urllib）
**数据源:** 东方财富高管/股东信息 API

**命令：**

```bash
python tools/personnel_data.py executives 600519 --json   # 高管信息
python tools/personnel_data.py shareholders 600519 --json  # 股东信息
python tools/personnel_data.py full 600519 --json          # 完整报告
```

**返回结构（full 模式）：**

- `executives[]` — 姓名/职务/任期/薪酬/持股变动
- `ownership.top10_shareholders[]` — 前十大股东及持股比例
- `ownership.controlling_shareholder` — 实际控制人
- `ownership.pledge_ratio` — 大股东质押比例
- `capital_actions.dividend_history_5y[]` — 近5年分红记录
- `capital_actions.total_shares_dilution_5y` — 股本稀释率
- `red_flags[]` — 异常信号（如有）

### 3.3 industry_data.py

**依赖:** 零外部依赖（urllib）
**数据源:** 东方财富行业板块 API

**命令：**

```bash
python tools/industry_data.py 白酒 --json          # 行业概况
python tools/industry_data.py search 新能源 --json  # 搜索行业
```

**返回结构：**

- `industry` — 行业名称
- `company_count` — 行业内公司数
- `averages` — ROE/毛利率/净利率/PE/负债率/营收增速
- `top_by_market_cap[]` — 市值排名前 N
- `top_by_roe[]` — ROE 排名前 N

**用途：** moat-analysis 中"vs 行业均值"从此有真实数据源；quality-screen 可基于行业均值动态调整阈值。

---

## 4. 分析层设计

### 4.1 management-check — 管理层审查

**芒格映射:** "我们只投资我们信任的管理层。"
**权重:** 15%（综合评分）
**数据来源:** personnel_data.py + quality-screen 的财务数据 + WebSearch

**5 项审查指标：**

| # | 维度 | 权重 | 量化规则 |
|---|------|------|---------|
| 1 | 资本配置能力 | 25% | ROIC/WACC 近5年均 > 1.2；大型并购（>净资产10%）无重大商誉减值 |
| 2 | 股权激励合理性 | 20% | 近5年总股本 CAGR < 2%/年 |
| 3 | 分红与回购 | 20% | 分红率 30-70%；回购在低价位进行 |
| 4 | 言行一致性 | 20% | 年报承诺 vs 实际执行；关联交易是否异常 |
| 5 | 大股东行为 | 15% | 质押 < 30%；近2年无连续大额减持 |

**评分方法:** PASS = 1分, CAUTION = 0.5分, FAIL = 0分 → 加权求和 × 10

**输出:** 管理层信任等级（A/B/C/D/F）+ 红旗信号清单 + 芒格视角总结

### 4.2 inversion-test — 逆向思维验证

**芒格映射:** "反过来想，总是反过来想。"
**权重:** 10%（综合评分）
**数据来源:** WebSearch（纯推理 + 搜索验证）

**5 类风险场景：**

| # | 风险类型 | 权重 | 核心问题 |
|---|---------|------|---------|
| 1 | 行业颠覆 | 25% | 5-10年内什么技术/模式可能让公司过时？ |
| 2 | 监管打击 | 25% | 是否面临教育双减/医疗集采/反垄断类政策风险？ |
| 3 | 关键人物 | 15% | 创始人/核心高管离职或出事的概率和影响？ |
| 4 | 集中度 | 20% | 单客/单供/单品/单地区 > 阈值？ |
| 5 | 财务疑点 | 15% | 存贷双高？应收异常？审计师频繁更换？ |

**评分规则:** 每个场景 0-10（0=高度危险，10=完全安全）→ 加权求和
总分直接映射为 inversion-test 贡献分

**输出:** 风险地图（概率×影响矩阵）+ 每场景详细论证 + 反脆弱特征分析

### 4.3 global-benchmark — 全球龙头对标

**芒格映射:** "理解一家公司最好的方式是跟全球最好的对手比。"
**权重:** 10%（综合评分）
**数据来源:** global_data.py（yfinance）+ ashare_data.py（A股方）

**5 个对标维度：**

| 维度 | 权重 | 规则 |
|------|------|------|
| 盈利能力对比 | 30% | ROE/毛利率/净利率 vs 全球龙头 |
| 估值对比 | 20% | PE/PB/PS vs 全球龙头 |
| 成长性对比 | 20% | 近3年营收/利润 CAGR vs 全球龙头 |
| 研发/国际化 | 15% | 研发费率 + 海外营收占比 |
| 市值差距 | 15% | 绝对值差距 + 倍数分析 |

**无对标物处理：**
如果行业无全球可比龙头（如白酒），返回"不适用"。该维度权重归零，其余 5 维度按比例重分配权重（÷0.9）。

**输出:** 对标表 + 雷达图对比数据 + 差距清单 + 追赶可能性评估

---

## 5. 修改的现有文件

### 5.1 munger-orchestrator.md

**4 处修改：**

1. **Phase 1** — 数据收集从 3 路扩至 5 路并行：`quote | financials | valuation | personnel(full) | industry_data`
2. **Phase 3** — 并行分析从 2 路扩至 4 路：`moat-analysis | safety-margin | management-check | inversion-test`
3. **Phase 4** — 激活全球对标逻辑（检查行业类型决定是否触发）
4. **Phase 5** — 评分表补全为 6/6 维度；global-benchmark 不适用时权重重分配规则

### 5.2 templates/report-base.html

- 侧栏导航新增 3 项链接
- 内容区域新增 3 个 section：`{{MANAGEMENT_CHECK_CONTENT}}`、`{{INVERSION_TEST_CONTENT}}`、`{{GLOBAL_BENCHMARK_CONTENT}}`

### 5.3 skills/report-generator.md

- 输入要求新增 3 个变量映射
- global-benchmark 不适用时传空字符串

### 5.4 CLAUDE.md

- Skills 表新增 3 行
- 工具脚本表新增 3 个命令

---

## 6. 综合评分完整版（第二批后）

| 维度 | 权重 | 得分来源 | 状态 |
|------|------|---------|------|
| 质量筛选 | 20% | quality-screen | ✅ 第一批 |
| 护城河宽度 | 25% | moat-analysis | ✅ 第一批 |
| 安全边际 | 20% | safety-margin | ✅ 第一批 |
| 管理层质量 | 15% | management-check | 🆕 第二批 |
| 逆向风险 | 10% | inversion-test | 🆕 第二批 |
| 全球对标 | 10% | global-benchmark | 🆕 第二批 |

**特殊情况：** global-benchmark 返回"不适用"时 → 权重归零，其余 5 维度按比例重分配（÷0.9）。

**评级映射（不变）：**
- 8-10: 强烈推荐
- 6-8: 可以买入
- 4-6: 继续观察
- < 4: 回避

---

## 7. 实施顺序

| 顺序 | 文件 | 依赖 | 说明 |
|------|------|------|------|
| 1 | tools/global_data.py | — | 需 pip install yfinance |
| 2 | tools/personnel_data.py | — | 零依赖，可与 1 并行 |
| 3 | tools/industry_data.py | — | 零依赖，可与 1/2 并行 |
| 4 | skills/management-check.md | Task 2 | 依赖 personnel_data.py |
| 5 | skills/inversion-test.md | — | 纯 WebSearch，无工具依赖 |
| 6 | skills/global-benchmark.md | Task 1 | 依赖 global_data.py |
| 7-10 | 4 个修改文件 | Tasks 4-6 | 依赖所有新建文件就绪 |

---

## 8. 设计原则

- 工具层保持统一 CLI 风格（`--json`、结构化错误）
- 分析 Skill 保持统一模板结构（角色→输入→规则→输出）
- global_data.py 是唯一新增外部依赖（yfinance），其余零依赖
- 无全球对标物时不强凑，优雅降级
- 管理层审查同时利用结构化和非结构化数据

---

## 9. 文档版本

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-07-10 | 初始设计 |

---

*Design by AI Munger brainstorming session. Inspired by [ai-berkshire](https://github.com/xbtlin/ai-berkshire).*
