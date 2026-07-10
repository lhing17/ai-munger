# AI Munger 第一批实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建查理芒格投资分析 Agent 的第一批——用户问一只 A 股，产出完整的交互式 HTML 投资分析报告。

**Architecture:** 5 层分层架构（工具→数据→分析→编排→报告），自底向上实施。先改进底层数据工具（增加 JSON 输出），再逐层构建数据 Skills、分析 Skills、编排器，最后以报告模板和 CLAUDE.md 收尾。

**Tech Stack:** Python 3 stdlib（工具层）、Claude Code Skills / Markdown（技能层）、HTML + Chart.js CDN（报告层）

**总文件数:** 10 个新建 + 1 个改进

---

## 文件清单

| # | 文件 | 操作 | 职责 |
|---|------|------|------|
| 1 | `tools/ashare_data.py` | 改进 | A 股数据 CLI：增加 --json、urllib 替代 curl、--period |
| 2 | `skills/a-share-data.md` | 新建 | 数据 Skill：封装工具调用，输出标准化 JSON |
| 3 | `skills/financial-query.md` | 新建 | 数据 Skill：财务交叉验证 |
| 4 | `skills/quality-screen.md` | 新建 | 分析 Skill：7 指标量化去劣筛选 |
| 5 | `skills/moat-analysis.md` | 新建 | 分析 Skill：5 维度护城河分析 |
| 6 | `skills/safety-margin.md` | 新建 | 分析 Skill：安全边际 + 价格区间 |
| 7 | `templates/report-base.html` | 新建 | 报告模板：CSS + JS + 页面骨架 |
| 8 | `skills/report-generator.md` | 新建 | 报告 Skill：数据填充到模板 |
| 9 | `skills/munger-orchestrator.md` | 新建 | 编排 Skill：对话管理 + 5 阶段工作流 |
| 10 | `CLAUDE.md` | 新建 | 项目入口：说明与 Skill 索引 |

---

### Task 1: 改进 ashare_data.py — 增加 --json 输出

**文件:**
- Modify: `tools/ashare_data.py`

**背景:** 当前脚本输出人类可读的格式化文本。Agent 需要结构化数据才能驱动后续分析。需要增加 `--json` 参数，同时用 `urllib` 替代 `curl` 消除 Windows 平台依赖。

- [ ] **Step 1: 替换 curl 调用为 urllib**

将 `_curl()` 和 `_curl_json()` 函数从 subprocess 调用 curl 改为使用 `urllib.request`：

```python
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from decimal import Decimal, ROUND_HALF_EVEN

_TIMEOUT = 15


def _fetch(url):
    """用 urllib 直连获取响应文本。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")

    # 腾讯行情 API 返回 GBK，其他返回 UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    """获取 JSON 响应。"""
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))
```

删除 `import subprocess`（不再需要）。

- [ ] **Step 2: 验证替换后的基本功能**

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py quote 600519
```
Expected: 与原来相同的格式化输出。

- [ ] **Step 3: 为所有命令添加 --json 输出模式**

在所有 `cmd_*` 函数中增加 JSON 输出路径。修改 `main()` 添加全局 `--json` 参数：

```python
def cmd_quote(code: str, as_json: bool = False):
    """实时行情快照。"""
    qq_code = _qq_code(code)
    raw = _fetch(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    if not d:
        error_exit(f"未找到股票 {code}", as_json)
        return

    if as_json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"实时行情: {d['name']} ({d['code']})")
    print("=" * 60)
    print(f"  当前价:     {d['price']}")
    print(f"  涨跌幅:     {d['change_pct']}%")
    print(f"  涨跌额:     {d['change_amt']}")
    print(f"  今开:       {d['open']}")
    print(f"  最高:       {d['high']}")
    print(f"  最低:       {d['low']}")
    print(f"  昨收:       {d['prev_close']}")
    print(f"  成交量:     {d['volume']} 手")
    print(f"  成交额:     {d['turnover_amt']}万")
    print(f"  总市值:     {d['market_cap']}亿")
    print(f"  流通市值:   {d['float_cap']}亿")
    print(f"  PE(动):     {d['pe']}")
    print(f"  PB:         {d['pb']}")
    print(f"  换手率:     {d['turnover_rate']}%")
    print(f"  52周最高:   {d['high_52w']}")
    print(f"  52周最低:   {d['low_52w']}")


def error_exit(msg: str, as_json: bool = False):
    """统一错误输出。"""
    if as_json:
        print(json.dumps({"error": msg}, ensure_ascii=False))
    else:
        print(f"❌ {msg}")
    sys.exit(1)
```

所有 `cmd_*` 函数签名增加 `as_json: bool = False` 参数，并在函数开头增加 JSON 分支。

- [ ] **Step 4: 修改 main() 支持 --json 和 --period**

```python
def main():
    parser = argparse.ArgumentParser(
        description="A股数据工具 — 腾讯行情 + 东方财富财务数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    sub = parser.add_subparsers(dest="command")

    p_quote = sub.add_parser("quote", help="实时行情")
    p_quote.add_argument("code", help="股票代码，如 600519")

    p_fin = sub.add_parser("financials", help="核心财务数据（近5年）")
    p_fin.add_argument("code", help="股票代码")
    p_fin.add_argument("--period", default="年报", choices=["年报", "半年报", "季报", "全部"],
                       help="报表周期（默认: 年报）")

    p_val = sub.add_parser("valuation", help="估值指标")
    p_val.add_argument("code", help="股票代码")

    p_search = sub.add_parser("search", help="搜索股票代码")
    p_search.add_argument("keyword", help="公司名或关键词")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "quote": lambda: cmd_quote(args.code, as_json=args.json),
        "financials": lambda: cmd_financials(args.code, as_json=args.json, period=args.period),
        "valuation": lambda: cmd_valuation(args.code, as_json=args.json),
        "search": lambda: cmd_search(args.keyword, as_json=args.json),
    }
    cmds[args.command]()
```

更新 `cmd_financials` 增加 `period` 参数：

```python
def cmd_financials(code: str, as_json: bool = False, period: str = "年报"):
    """近5年核心财务数据。"""
    qq_code = _qq_code(code)
    raw = _fetch(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    name = d.get("name", code) if d else code

    code_clean = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    market = "SH" if code_clean.startswith(("6", "9", "5")) else "SZ"

    # 东方财富 datacenter API
    fin_url = "https://datacenter.eastmoney.com/securities/api/data/get"
    period_filter = {
        "年报": '(REPORT_TYPE="年报")',
        "半年报": '(REPORT_TYPE="半年报")',
        "季报": '(REPORT_TYPE="季报")',
        "全部": "",
    }.get(period, '(REPORT_TYPE="年报")')

    filter_str = f'(SECUCODE="{code_clean}.{market}"){period_filter}'
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "ALL",
        "filter": filter_str,
        "p": "1",
        "ps": "5" if period == "年报" else "10",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }
    reports = []
    try:
        data = _fetch_json(fin_url, params)
        reports = data.get("result", {}).get("data", [])
    except Exception:
        pass

    # 如果筛选无结果，去掉周期限制
    if not reports and period_filter:
        params["filter"] = f'(SECUCODE="{code_clean}.{market}")'
        try:
            data = _fetch_json(fin_url, params)
            reports = data.get("result", {}).get("data", [])
        except Exception:
            pass

    if as_json:
        output = []
        for r in reports[:10]:
            output.append({
                "report_date": r.get("REPORT_DATE", "")[:10],
                "report_name": r.get("REPORT_DATE_NAME", ""),
                "revenue": r.get("TOTALOPERATEREVE"),
                "revenue_growth": r.get("TOTALOPERATEREVETZ"),
                "net_profit": r.get("PARENTNETPROFIT"),
                "profit_growth": r.get("PARENTNETPROFITTZ"),
                "eps": r.get("EPSJB"),
                "bps": r.get("BPS"),
                "roe": r.get("ROEJQ"),
            })
        print(json.dumps({"name": name, "code": code_clean, "reports": output}, ensure_ascii=False, indent=2))
        return

    # ... 保持原有的格式化输出逻辑 ...
```

- [ ] **Step 5: 验证 JSON 模式**

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py quote 600519 --json
```
Expected: 结构化 JSON 输出到 stdout。

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py financials 600519 --json --period 年报
```
Expected: JSON 数组包含近 5 年财务数据。

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py search 茅台 --json
```
Expected: JSON 搜索结果。

- [ ] **Step 6: 验证 --period 参数**

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py financials 600519 --period 季报
```
Expected: 最多 10 条季报数据。

---

### Task 2: 创建 a-share-data.md — A 股数据 Skill

**文件:**
- Create: `skills/a-share-data.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: a-share-data
description: 获取 A 股数据 — 封装 ashare_data.py 工具，为分析层提供标准化的股票行情、财务、估值和搜索数据
---

# A 股数据获取

你是 A 股数据获取层。你的职责是调用 `tools/ashare_data.py` 工具脚本，为上层分析 Skills 提供结构化数据。

## 调用规范

所有数据查询通过 Bash 工具执行，统一使用 `--json` 参数：

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py <command> <args> --json
```

## 可用命令

### 1. 实时行情 (quote)

```bash
python tools/ashare_data.py quote <股票代码> --json
```

返回字段：`name`, `code`, `price`, `prev_close`, `open`, `high`, `low`, `volume`, `turnover_amt`, `market_cap`, `float_cap`, `pe`, `pb`, `turnover_rate`, `high_52w`, `low_52w`, `change_pct`, `change_amt`

### 2. 核心财务 (financials)

```bash
python tools/ashare_data.py financials <股票代码> --json [--period 年报|季报|半年报|全部]
```

返回字段（每条 report）：`report_date`, `report_name`, `revenue`, `revenue_growth`, `net_profit`, `profit_growth`, `eps`, `bps`, `roe`

### 3. 估值指标 (valuation)

```bash
python tools/ashare_data.py valuation <股票代码> --json
```

返回与 quote 相同的字段，额外包含市值验算结果。

### 4. 搜索股票 (search)

```bash
python tools/ashare_data.py search <关键词> --json
```

返回匹配的股票代码和名称列表。

## 输出规范

每次调用后将原始 JSON 原样传递给调用方（分析 Skill 或编排器）。不做二次加工。只标注数据可用性：

- 某个命令执行失败时，返回 `{"error": "...", "source": "<command>", "available": false}`
- 不要阻断流程，让上层决定如何处理缺失数据

## 容错

- 工具脚本网络超时或返回错误时，捕获错误信息，以结构化 JSON 返回
- 不重试超过 1 次
- 命令不存在时提示用户检查工具脚本路径
```

- [ ] **Step 2: 验证 Skill 可被调用**

触发 Skill 并请求获取茅台行情：

```
User: "用 a-share-data 获取 600519 的行情"
```

Expected: Agent 执行 `python tools/ashare_data.py quote 600519 --json` 并返回结构化数据。

---

### Task 3: 创建 financial-query.md — 财务数据交叉验证 Skill

**文件:**
- Create: `skills/financial-query.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: financial-query
description: 财务数据交叉验证 — 对 A 股数据进行多渠道验证，标注置信度，补充工具脚本未覆盖的深度数据
---

# 财务数据交叉验证

你是财务数据质量守护者。你的职责是对 `a-share-data` 获取的数据进行交叉验证，标注每条数据的置信度，并在工具数据不足时通过 WebSearch 补充关键信息。

## 工作流程

### Step 1: 接收数据

从 `a-share-data` Skill 获取的原始数据。

### Step 2: 关键指标交叉验证

对以下关键指标进行双重确认：

| 指标 | 主要来源 | 验证方法 |
|------|---------|---------|
| ROE | ashare_data.py (东方财富) | WebSearch 查最新年报 ROE 核对 |
| 营收 | ashare_data.py (东方财富) | WebSearch 查最新财报营收核对 |
| PE | ashare_data.py (腾讯行情) | WebSearch 查当前 PE(TTM) 核对 |
| 总市值 | ashare_data.py (腾讯行情) | 用 股价×总股本 验算 |

### Step 3: 标注置信度

为每条关键数据标注置信度：

- ✅ **多源一致**: 两个以上独立数据源结果偏差 < 5%
- ⚠️ **单源**: 仅从工具脚本获取，未做交叉验证
- ❓ **估计值**: 通过推算得出（如 DCF 估值），非直接观测数据
- ❌ **不可用**: 数据获取失败或明显异常

### Step 4: 补充深度数据（按需）

当分析层需要以下工具脚本未覆盖的数据时，使用 WebSearch 补充：

- **股权结构**: 前十大股东、实际控制人、机构持仓比例
- **分红历史**: 近 5 年分红金额、股息率、分红率
- **商誉明细**: 商誉构成、减值风险
- **关联交易**: 大额关联交易披露
- **质押情况**: 大股东质押比例

搜索关键词模板：`<股票名称> <股票代码> <数据项> 2024 2025`

## 输出格式

```markdown
## 数据质量报告

| 指标 | 值 | 来源 | 置信度 |
|------|-----|------|--------|
| ROE | 22.5% | 东方财富 + 年报 | ✅ 多源一致 |
| 营收 | 1250亿 | 东方财富 | ⚠️ 单源 |
| PE(TTM) | 28.3 | 腾讯行情 | ⚠️ 单源 |
| 总市值 | 2.1万亿 | 腾讯行情(验算一致) | ✅ 多源一致 |

## 补充数据

- 前十大股东合计持股: XX%
- 近 5 年累计分红: XX 亿
- ...
```

## 容错

- WebSearch 查不到时标注为 "未查到公开数据"，不编造
- 交叉验证发现重大偏差（>20%）时特别标注 ⚠️ 偏差警告
```

---

### Task 4: 创建 quality-screen.md — 量化去劣筛选 Skill

**文件:**
- Create: `skills/quality-screen.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: quality-screen
description: 芒格量化去劣筛选 — 用 7 条量化指标快速排除非一流公司，输出 PASS/FAIL/CAUTION 判定和得分卡
---

# 芒格量化去劣筛选

你是查理·芒格风格的量化质量分析师。你的信条是："买好公司的第一步是排除烂公司"。你使用 7 条简单但有效的量化标准，像筛子一样淘汰不合格的公司。

## 输入要求

需要以下数据（由 `a-share-data` 和 `financial-query` 提供）：

- 近 5 年 ROE（每年）
- 近 5 年净利润（每年）
- 近 5 年自由现金流或经营活动现金流
- 最新报表：资产负债率、有息负债率
- 近 5 年毛利率（每年）
- 最新报表：应收账款、营业收入、商誉、净资产

## 7 条筛选标准

### 1. ROE 稳定性 ⚖️ (权重 20%)
**规则**: 近 5 年 ROE 每年均 > 12%，且标准差/均值 < 0.4
- ✅ PASS: 5 年均 > 12%，波动小
- ⚠️ CAUTION: 有 1-2 年略低于 12%，或波动较大
- ❌ FAIL: 多 年 < 12% 或剧烈波动

### 2. 盈利能力 💰 (权重 15%)
**规则**: 净利润近 5 年 CAGR > 0，且最近一年为正
- ✅ PASS: 5 年 CAGR > 5%
- ⚠️ CAUTION: 增速 0-5%
- ❌ FAIL: 负增长或亏损

### 3. 财务健康 🏦 (权重 15%)
**规则**: 
- 有息负债率 < 50%（总有息负债/总资产）
- 资产负债率 < 70%
- ✅ PASS: 两项均满足
- ⚠️ CAUTION: 一项不满足
- ❌ FAIL: 两项均不满足

### 4. 现金流质量 💸 (权重 15%)
**规则**: 近 5 年累计经营现金流/累计净利润 > 0.6
- ✅ PASS: 比率 > 0.8
- ⚠️ CAUTION: 比率 0.6-0.8
- ❌ FAIL: 比率 < 0.6

### 5. 毛利率稳定性 📊 (权重 10%)
**规则**: 近 5 年毛利率标准差 < 5 个百分点
- ✅ PASS: 标准差 < 3pp
- ⚠️ CAUTION: 标准差 3-5pp
- ❌ FAIL: 标准差 > 5pp

### 6. 盈利真实性 🔍 (权重 15%)
**规则**: 应收账款/营业收入 < 30%
- ✅ PASS: < 15%
- ⚠️ CAUTION: 15%-30%
- ❌ FAIL: > 30%

### 7. 商誉风险 🎲 (权重 10%)
**规则**: 商誉/净资产 < 30%
- ✅ PASS: < 15%
- ⚠️ CAUTION: 15%-30%
- ❌ FAIL: > 30%

## 行业例外

| 行业 | 调整规则 |
|------|---------|
| 金融（银行/保险/券商） | 跳过规则 3（负债率），改用 ROA 替代 ROE 看规则 1 |
| 科技/医药初创 | 规则 1 可接受 ROE 前低后高的改善趋势 |
| 重资产行业（钢铁/化工） | 规则 3 资产负债率阈值放宽至 75% |
| 零售/消费 | 规则 6 应收账款放宽至 25% |

## 判定规则

- **PASS**: 总分 ≥ 5 分（满分 10 分），无 FAIL 项
- **FAIL**: 总分 < 3 分，或有 3 项以上 FAIL
- **CAUTION**: 介于 PASS 和 FAIL 之间

评分方法：
- PASS = 1 分, CAUTION = 0.5 分, FAIL = 0 分
- 乘以各规则权重后求和 → 满分 10 分

## 输出格式

```markdown
## 质量筛选结果: <股票名称> (<股票代码>)

**判定: ✅ PASS / ⚠️ CAUTION / ❌ FAIL**
**总分: X.X / 10**

| # | 指标 | 结果 | 得分 | 关键数据 |
|---|------|------|------|---------|
| 1 | ROE 稳定性 | ✅ | 2.0 | 近5年ROE: [15,18,22,20,19]% |
| 2 | 盈利能力 | ✅ | 1.5 | 净利润CAGR: 8.3% |
| 3 | 财务健康 | ⚠️ | 0.75 | 有息负债率: 35% |
| 4 | 现金流质量 | ✅ | 1.5 | 经营现金流/净利润: 1.1 |
| 5 | 毛利率稳定 | ✅ | 1.0 | 毛利率: 70±1.5% |
| 6 | 盈利真实性 | ✅ | 1.5 | 应收/营收: 8% |
| 7 | 商誉风险 | ❌ | 0 | 商誉/净资产: 45% |

## 芒格视角

[基于以上数据，模仿查理芒格的风格给出 2-3 句话的定性判断。简洁、直接、不留情面。]
```

## 注意事项

- 数据不足的指标标记为 "⚠️ 数据不足，跳过"
- 不给不确定的指标 "人情分"——缺数据 = 不给分
- 行业判断由你根据公司主营业务自主判断，不需要用户告知
```

---

### Task 5: 创建 moat-analysis.md — 护城河分析 Skill

**文件:**
- Create: `skills/moat-analysis.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: moat-analysis
description: 芒格护城河深度分析 — 从 5 个维度评估企业竞争优势的宽度、深度和可持续性
---

# 芒格护城河分析

你是查理·芒格风格的护城河分析师。芒格说："伟大的公司都有宽阔的护城河。"你的任务是评估一家公司的竞争优势有多强、能持续多久。

## 输入要求

需要以下数据（由 `a-share-data` 和 `financial-query` 提供）：

- 近 5 年毛利率 + 行业平均水平
- 近 5 年 ROE + 行业平均水平
- 近 5 年营收增速 + 行业平均增速
- 研发费用/营收（如有）
- 销售费用/营收
- 公司业务描述、行业地位
- 主要竞争对手

## 5 维度评估

### 1. 品牌溢价 🏷️ (权重 25%)

**核心问题: 这家公司能涨价而不丢客户吗？**

量化线索：
- 毛利率持续高于行业均值 → 品牌有定价权
- 销售费用率低但营收增长好 → 品牌自带流量
- 毛利率趋势上升 → 品牌在变强

评分标准 (1-10)：
- 9-10: 强大品牌，毛利率远超行业 (>15pp)，消费品/奢侈品龙头
- 6-8: 有一定品牌认知，毛利率高于行业 (5-15pp)
- 3-5: 品牌一般，毛利率与行业持平
- 1-2: 无品牌，毛利率低于行业

### 2. 转换成本 🔒 (权重 25%)

**核心问题: 客户换供应商有多痛苦？**

量化线索：
- 高客户留存率/续费率
- 产品嵌入客户核心业务流程（企业软件、关键零部件）
- 切换需要重新培训/认证/集成

评分标准 (1-10)：
- 9-10: 极高转换成本（如企业操作系统、核心数据库）
- 6-8: 较高转换成本（如银行账户、关键供应商认证）
- 3-5: 中等（如常用消费品品牌，可替代但需要适应）
- 1-2: 无转换成本（如大宗商品、标准化产品）

### 3. 网络效应 🌐 (权重 20%)

**核心问题: 用户越多，产品越好用吗？**

量化线索：
- 双边平台（买家越多→卖家越多→买家越多）
- 用户规模是竞争对手的倍数
- 数据网络效应（越多用户→越多数据→越好产品）

评分标准 (1-10)：
- 9-10: 强大网络效应（如社交平台、交易所）
- 6-8: 明显网络效应（如电商平台、支付网络）
- 3-5: 微弱网络效应
- 1-2: 无网络效应

### 4. 规模优势 📐 (权重 15%)

**核心问题: 规模大本身是不是优势？**

量化线索：
- 营收/市值在行业中排名前 3
- 毛利率随规模增长而提升（规模经济）
- 管理费用率随规模增长而下降
- 单位成本低于竞争对手

评分标准 (1-10)：
- 9-10: 绝对规模优势，成本行业最低
- 6-8: 明显规模优势
- 3-5: 有一定规模但优势不明显
- 1-2: 无规模优势

### 5. 特许经营权 📜 (权重 15%)

**核心问题: 有别人拿不到的牌照/专利/授权吗？**

量化线索：
- 政府特许经营（免税牌照、金融牌照、烟草专卖）
- 核心专利数量和保护期
- 独家授权/专营协议
- 行业准入门槛（是否只有少数玩家能做）

评分标准 (1-10)：
- 9-10: 独家或极少数玩家可经营的强管制行业
- 6-8: 明显的牌照/专利壁垒
- 3-5: 有一定的准入门槛
- 1-2: 无准入门槛

## 输出格式

```markdown
## 护城河分析: <股票名称>

**护城河总分: X.X / 10 | 评级: (宽阔/中等/狭窄/无)**

| 维度 | 得分 | 权重 | 加权 | 判断依据 |
|------|------|------|------|---------|
| 品牌溢价 | 8 | 25% | 2.0 | 毛利率 72%，行业均值 45% |
| 转换成本 | 3 | 25% | 0.75 | 产品标准化，客户可随时换 |
| 网络效应 | 2 | 20% | 0.4 | 传统制造业，无网络效应 |
| 规模优势 | 9 | 15% | 1.35 | 行业第一，产能是第二名的 3 倍 |
| 特许经营 | 5 | 15% | 0.75 | 有一些专利但即将到期 |

**加权总分: 5.25 / 10 — 中等护城河**

## 护城河趋势

- 🔼 变宽: [列出支撑理由]
- 🔽 变窄: [列出威胁因素]
- ➡️ 稳定: [判断整体趋势]

## 芒格视角

[2-3 句话的芒格风格总结——这家公司的护城河有多宽？什么可能摧毁它？]
```

## 数据不足处理

- 某个维度缺数据 → "数据不足，无法评估该维度"，该维度得分记为 0
- 行业平均数据获取不到 → 用常识估算（标注"估计"）
- 竞争对手数据不全 → 基于已知信息做保守估计
```

---

### Task 6: 创建 safety-margin.md — 安全边际评估 Skill

**文件:**
- Create: `skills/safety-margin.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: safety-margin
description: 芒格安全边际评估 — DCF + PE + 清算价值三法估值，输出买入价格区间（激进/稳健/保守三档）
---

# 芒格安全边际评估

你是查理·芒格风格的价值评估师。芒格说："以合理价格买伟大公司，比以便宜价格买普通公司好得多。"你的任务不是精确估值，而是判断当前价格是否提供了足够的安全边际，并给出不同风险偏好的参考买入区间。

## 输入要求

需要以下数据（由 `a-share-data` 和 `financial-query` 提供）：

- 当前股价、总股本、总市值
- 近 3 年自由现金流（如无则用经营现金流 × 0.7 估算）
- 近 5 年 PE（每年高低点 + 中位数）
- 近 5 年净利润、营收增速
- 最新报表：流动资产、总负债、固定资产、商誉
- 当前 PE(TTM)、PB、PS
- 近 5 年 ROE
- 股息率（如有）

## 估值方法

### 方法 1: DCF 粗略估算

使用简化的两阶段 DCF：

1. **基期 FCF**: 取近 3 年自由现金流均值
2. **增长假设**:
   - 悲观: 永续增长 2%（GDP 增长率的底线）
   - 中性: 永续增长 4%（稳定增长公司）
   - 乐观: 前 5 年高增长（取近 3 年 FCF CAGR 的一半），之后永续 3%
3. **折现率**: 统一 10%（芒格推崇的股权资本成本）
4. **计算**:
   - 终值 = 第5年FCF × (1+永续增长率) / (折现率 - 永续增长率)
   - 企业价值 = 5年FCF现值 + 终值现值
   - 每股价值 = (企业价值 + 现金 - 有息负债) / 总股本

### 方法 2: PE 估值法

1. **合理 PE**: 取近 5 年 PE(TTM) 中位数，参考行业平均 PE 调整
2. **预期 EPS**: 
   - 优先使用近 3 年 EPS CAGR 外推（乐观）
   - 保守使用最近年度 EPS（悲观）
3. **合理股价** = 合理 PE × 预期 EPS

### 方法 3: 清算价值底线（仅保守型使用）

1. **清算价值** = (流动资产 - 总负债 + 固定资产 × 0.3 - 商誉) / 总股本
2. **适用条件**: 仅当清算价值 > 0 时有效
3. **使用方式**: 作为保守型投资者的价格参考下限

## 三档买入价格区间

取方法 1（DCF）和方法 2（PE）的估值中枢，做交叉验证：

### 🔥 激进型（安全边际 15%）
- 买入价格 ≤ DCF/PE 估值中枢 × 0.85
- 适用：高成长确定性 + 强护城河公司
- 风险：市场波动时可能仍有下行

### ⚖️ 稳健型（安全边际 30%）  
- 买入价格 ≤ DCF/PE 估值中枢 × 0.70
- 适用：有一定确定性 + 中等护城河
- 风险：可能等不到这个价格

### 🛡️ 保守型（安全边际 50%）
- 买入价格 ≤ max(DCF/PE 估值中枢 × 0.50, 清算价值底线)
- 适用：要求极高容错空间
- 风险：好公司很少跌到这么低

## 当前价 vs 估值

计算当前股价与各档的关系：
- 当前价高于激进价 → "当前价格偏贵，建议等待回调"
- 当前价在激进和稳健之间 → "激进型投资者可考虑，稳健型建议等待"
- 当前价在稳健和保守之间 → "已具备一定安全边际，稳健型可关注"
- 当前价低于保守价 → "市场价格低于保守估值底线，值得深入研究（但需检查是否有我们漏掉的重大风险）"

## 输出格式

```markdown
## 安全边际评估: <股票名称>

### 估值摘要

| 方法 | 估值中枢(元/股) | 估值区间 |
|------|----------------|---------|
| DCF | XXX | XXX-XXX |
| PE | XXX | XXX-XXX |
| 交叉验证中枢 | XXX | — |

### 买入价格区间

| 类型 | 买入价格 ≤ | 安全边际 | vs 当前价 |
|------|-----------|---------|----------|
| 🔥 激进 | ¥X.XX | 15% | +12.5% (当前价更低/更高) |
| ⚖️ 稳健 | ¥Y.YY | 30% | -5.2% |
| 🛡️ 保守 | ¥Z.ZZ | 50% | -28.7% |

当前股价: ¥XX.XX

### 综合判断

**当前安全边际水平: (充足/一般/不足/不存在)**

[基于当前价格与估值的关系，给出芒格风格的判断]

### 注意事项
- ⚠️ 以上估值基于公开历史数据，不构成投资建议
- ⚠️ DCF 对增长率和折现率假设高度敏感，实际偏差可能很大
- ⚠️ 估值是艺术而非科学——格雷厄姆说"大致正确好过精确错误"
```

## 不展示价格区间的情况

在以下情况，明确说明无法给出价格区间：
- 净利润为负且无扭亏预期
- 自由现金流持续为负（近 3 年均负）
- 财务数据不足（少于 3 年历史数据）
- 综合评分 < 4 分（来自 quality-screen）
```

---

### Task 7: 创建 report-base.html — HTML 报告模板

**文件:**
- Create: `templates/report-base.html`

- [ ] **Step 1: 创建 HTML 模板骨架**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{STOCK_NAME}} ({{STOCK_CODE}}) — 芒格投资分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0d1117;
    --panel: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-secondary: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d2991d;
    --red: #f85149;
    --purple: #a371f7;
    --sidebar-width: 220px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    display: flex;
    min-height: 100vh;
  }

  /* === Sidebar === */
  nav#sidebar {
    width: var(--sidebar-width);
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 24px 0;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    overflow-y: auto;
    z-index: 100;
  }

  nav#sidebar .logo {
    padding: 0 20px 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
  }

  nav#sidebar .logo h2 {
    font-size: 16px;
    color: var(--text);
  }

  nav#sidebar .logo span {
    font-size: 11px;
    color: var(--text-secondary);
  }

  nav#sidebar a {
    display: block;
    padding: 8px 20px;
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 13px;
    transition: all 0.15s;
    border-left: 3px solid transparent;
  }

  nav#sidebar a:hover,
  nav#sidebar a.active {
    color: var(--text);
    background: rgba(88, 166, 255, 0.08);
    border-left-color: var(--accent);
  }

  /* === Main Content === */
  main {
    margin-left: var(--sidebar-width);
    flex: 1;
    padding: 32px 40px;
    max-width: 960px;
  }

  /* === Sections === */
  .section {
    margin-bottom: 48px;
    padding-bottom: 32px;
    border-bottom: 1px solid var(--border);
  }

  .section:last-child { border-bottom: none; }

  .section h2 {
    font-size: 22px;
    margin-bottom: 4px;
    color: var(--text);
  }

  .section .subtitle {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 20px;
  }

  /* === Summary Cards === */
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }

  .summary-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
  }

  .summary-card .label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 4px;
  }

  .summary-card .value {
    font-size: 20px;
    font-weight: 600;
  }

  .summary-card .value.green { color: var(--green); }
  .summary-card .value.yellow { color: var(--yellow); }
  .summary-card .value.red { color: var(--red); }

  /* === Score Bar === */
  .score-bar-container {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
  }

  .score-bar-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 14px;
  }

  .score-bar {
    height: 12px;
    border-radius: 6px;
    background: var(--border);
    overflow: hidden;
  }

  .score-bar-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.6s ease;
  }

  .score-zones {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 11px;
    color: var(--text-secondary);
  }

  .score-zones span { flex: 1; text-align: center; }

  /* === Tables === */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 13px;
  }

  th, td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 11px;
    text-transform: uppercase;
  }

  tr:hover td { background: rgba(88, 166, 255, 0.04); }

  /* === Collapsible === */
  details {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  details summary {
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    color: var(--accent);
    list-style: none;
  }

  details summary::-webkit-details-marker { display: none; }

  details summary::before {
    content: '▸ ';
    display: inline-block;
    transition: transform 0.2s;
  }

  details[open] summary::before {
    content: '▾ ';
  }

  details .detail-content {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }

  /* === Price Cards === */
  .price-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 16px 0;
  }

  .price-card {
    border-radius: 10px;
    padding: 20px;
    text-align: center;
  }

  .price-card.aggressive {
    background: linear-gradient(135deg, #3a1c1c, #5c2020);
    border: 1px solid var(--red);
  }

  .price-card.moderate {
    background: linear-gradient(135deg, #3a3010, #5c4a18);
    border: 1px solid var(--yellow);
  }

  .price-card.conservative {
    background: linear-gradient(135deg, #0d3320, #134a2e);
    border: 1px solid var(--green);
  }

  .price-card .investor-type {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .price-card.aggressive .investor-type { color: #ff6b6b; }
  .price-card.moderate .investor-type { color: #ffd700; }
  .price-card.conservative .investor-type { color: #3fb950; }

  .price-card .margin-note {
    font-size: 11px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .price-card .target-price {
    font-size: 28px;
    font-weight: 700;
    margin: 8px 0;
  }

  .price-card .method-note {
    font-size: 10px;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  /* === Charts === */
  .chart-container {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin: 16px 0;
  }

  .chart-container canvas {
    max-height: 320px;
  }

  /* === Footer === */
  footer {
    margin-top: 48px;
    padding: 24px 0;
    border-top: 1px solid var(--border);
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.8;
  }

  footer .disclaimer {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  /* === Badges === */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
  }

  .badge.pass { background: rgba(63, 185, 80, 0.15); color: var(--green); }
  .badge.fail { background: rgba(248, 81, 73, 0.15); color: var(--red); }
  .badge.caution { background: rgba(210, 153, 29, 0.15); color: var(--yellow); }

  /* === Responsive === */
  @media (max-width: 768px) {
    nav#sidebar { display: none; }
    main { margin-left: 0; padding: 16px; }
    .price-grid { grid-template-columns: 1fr; }
    .summary-grid { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>

<!-- Sidebar -->
<nav id="sidebar">
  <div class="logo">
    <h2>🧠 AI Munger</h2>
    <span>查理芒格投资分析</span>
  </div>
  <a href="#summary" class="active">📋 投资摘要</a>
  <a href="#quality">🔢 质量筛选</a>
  <a href="#moat">🏰 护城河分析</a>
  <a href="#safety">🛡️ 安全边际</a>
  <a href="#charts">📈 关键图表</a>
</nav>

<!-- Main Content -->
<main>

  <!-- ========== INVESTMENT SUMMARY ========== -->
  <section id="summary" class="section">
    <h2>📋 投资摘要</h2>
    <p class="subtitle">{{REPORT_DATE}} · 数据截至 {{DATA_DATE}}</p>

    <div class="summary-grid">
      <div class="summary-card">
        <div class="label">综合评分</div>
        <div class="value {{SCORE_COLOR}}">{{OVERALL_SCORE}} / 10</div>
      </div>
      <div class="summary-card">
        <div class="label">评级</div>
        <div class="value {{RATING_COLOR}}">{{RATING}}</div>
      </div>
      <div class="summary-card">
        <div class="label">当前股价</div>
        <div class="value">¥{{CURRENT_PRICE}}</div>
      </div>
      <div class="summary-card">
        <div class="label">总市值</div>
        <div class="value">{{MARKET_CAP}}</div>
      </div>
    </div>

    <div class="score-bar-container">
      <div class="score-bar-label">
        <span>质量 · 护城河 · 安全边际 · 综合评估</span>
        <span>{{OVERALL_SCORE}}/10</span>
      </div>
      <div class="score-bar">
        <div class="score-bar-fill" style="width: {{SCORE_PERCENT}}%; background: {{SCORE_COLOR_HEX}};"></div>
      </div>
      <div class="score-zones">
        <span style="color: var(--red);">回避 0-4</span>
        <span style="color: var(--yellow);">观察 4-6</span>
        <span style="color: var(--green);">买入 6-8</span>
        <span style="color: #00ff88;">强烈推荐 8-10</span>
      </div>
    </div>

    <div class="summary-card" style="margin-top: 16px;">
      <div class="label">一句话结论</div>
      <div style="font-size: 15px; margin-top: 8px;">{{ONE_LINER}}</div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;">
      <div class="summary-card">
        <div class="label">🟢 核心优势</div>
        <div style="font-size: 13px; margin-top: 8px;">{{CORE_STRENGTHS}}</div>
      </div>
      <div class="summary-card">
        <div class="label">🔴 核心风险</div>
        <div style="font-size: 13px; margin-top: 8px;">{{CORE_RISKS}}</div>
      </div>
    </div>
  </section>

  <!-- ========== QUALITY SCREEN ========== -->
  <section id="quality" class="section">
    <h2>🔢 质量筛选</h2>
    <p class="subtitle">7 指标量化去劣 — "买好公司的第一步是排除烂公司"</p>
    {{QUALITY_SCREEN_CONTENT}}
  </section>

  <!-- ========== MOAT ANALYSIS ========== -->
  <section id="moat" class="section">
    <h2>🏰 护城河分析</h2>
    <p class="subtitle">5 维度评估企业竞争优势 — "伟大的公司都有宽阔的护城河"</p>
    {{MOAT_ANALYSIS_CONTENT}}
  </section>

  <!-- ========== SAFETY MARGIN ========== -->
  <section id="safety" class="section">
    <h2>🛡️ 安全边际</h2>
    <p class="subtitle">DCF + PE + 清算价值三法估值 — "以合理价格买伟大公司"</p>
    {{SAFETY_MARGIN_CONTENT}}

    {{PRICE_RANGE_SECTION}}
  </section>

  <!-- ========== CHARTS ========== -->
  <section id="charts" class="section">
    <h2>📈 关键图表</h2>

    <div class="chart-container">
      <h3 style="font-size: 14px; margin-bottom: 12px;">关键指标 5 年趋势</h3>
      <canvas id="trendChart"></canvas>
    </div>

    <div class="chart-container">
      <h3 style="font-size: 14px; margin-bottom: 12px;">质量维度雷达图</h3>
      <canvas id="radarChart"></canvas>
    </div>
  </section>

  <!-- ========== FOOTER ========== -->
  <footer>
    <div class="disclaimer">
      <strong>⚠️ 免责声明</strong><br>
      本报告由 AI 基于公开数据自动生成，不构成投资建议。所有分析结论基于查理芒格的投资哲学框架，仅为信息参考。投资有风险，入市需谨慎。任何投资决策应由您独立判断并自行承担风险。
    </div>
    <p>数据来源: 腾讯行情 (qt.gtimg.cn) · 东方财富 (eastmoney.com) | 分析框架: 查理·芒格价值投资哲学</p>
    <p>生成时间: {{REPORT_DATE}} | AI Munger v1.0</p>
  </footer>

</main>

<!-- Chart Data & Init -->
<script>
// === Trend Chart ===
const trendCtx = document.getElementById('trendChart').getContext('2d');
new Chart(trendCtx, {
  type: 'line',
  data: {
    labels: {{TREND_YEARS}},
    datasets: [
      {
        label: '营收 (亿)',
        data: {{TREND_REVENUE}},
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88, 166, 255, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: '净利润 (亿)',
        data: {{TREND_PROFIT}},
        borderColor: '#3fb950',
        backgroundColor: 'rgba(63, 185, 80, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'ROE (%)',
        data: {{TREND_ROE}},
        borderColor: '#d2991d',
        backgroundColor: 'rgba(210, 153, 29, 0.1)',
        tension: 0.3,
        fill: true,
        yAxisID: 'y1'
      }
    ]
  },
  options: {
    responsive: true,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: {
        labels: { color: '#8b949e', usePointStyle: true, padding: 20 }
      }
    },
    scales: {
      x: {
        ticks: { color: '#8b949e' },
        grid: { color: 'rgba(48, 54, 61, 0.5)' }
      },
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: { display: true, text: '金额 (亿)', color: '#8b949e' },
        ticks: { color: '#8b949e' },
        grid: { color: 'rgba(48, 54, 61, 0.5)' }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: { display: true, text: 'ROE (%)', color: '#8b949e' },
        ticks: { color: '#8b949e' },
        grid: { drawOnChartArea: false }
      }
    }
  }
});

// === Radar Chart ===
const radarCtx = document.getElementById('radarChart').getContext('2d');
new Chart(radarCtx, {
  type: 'radar',
  data: {
    labels: {{RADAR_LABELS}},
    datasets: [{
      label: '{{STOCK_NAME}}',
      data: {{RADAR_DATA}},
      backgroundColor: 'rgba(88, 166, 255, 0.2)',
      borderColor: '#58a6ff',
      borderWidth: 2,
      pointBackgroundColor: '#58a6ff'
    }]
  },
  options: {
    responsive: true,
    scales: {
      r: {
        min: 0,
        max: 10,
        ticks: {
          stepSize: 2,
          color: '#8b949e',
          backdropColor: 'transparent'
        },
        grid: { color: 'rgba(48, 54, 61, 0.8)' },
        angleLines: { color: 'rgba(48, 54, 61, 0.8)' },
        pointLabels: { color: '#c9d1d9', font: { size: 12 } }
      }
    },
    plugins: {
      legend: { display: false }
    }
  }
});

// === Sidebar Active State ===
document.querySelectorAll('nav#sidebar a').forEach(link => {
  link.addEventListener('click', function() {
    document.querySelectorAll('nav#sidebar a').forEach(l => l.classList.remove('active'));
    this.classList.add('active');
  });
});

// === Scroll Spy ===
window.addEventListener('scroll', function() {
  const sections = document.querySelectorAll('main .section');
  const links = document.querySelectorAll('nav#sidebar a');
  let current = '';
  sections.forEach(section => {
    const top = section.offsetTop - 80;
    if (window.scrollY >= top) current = section.getAttribute('id');
  });
  links.forEach(link => {
    link.classList.remove('active');
    if (link.getAttribute('href') === '#' + current) link.classList.add('active');
  });
});

// === Print Optimization ===
window.addEventListener('beforeprint', function() {
  document.querySelectorAll('details').forEach(d => d.setAttribute('open', ''));
});
</script>

</body>
</html>
```

- [ ] **Step 2: 验证模板**

在浏览器中直接打开 `templates/report-base.html`——应该看到一个空壳页面（缺少数据填充，但结构和样式可见，无 JS 报错）。

---

### Task 8: 创建 report-generator.md — 报告生成 Skill

**文件:**
- Create: `skills/report-generator.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: report-generator
description: 芒格投资报告生成器 — 将分析层输出的所有结论文本和图表数据填充到 HTML 模板，生成交互式报告
---

# 芒格投资报告生成器

你是报告生成器。你的职责是接收编排器汇总的所有分析结论，将数据填充到 HTML 报告模板中，生成最终的单文件交互式报告。

## 输入要求

编排器在调用你之前会准备好以下数据：

### 1. 基础信息
- `STOCK_NAME`: 公司名称
- `STOCK_CODE`: 股票代码
- `REPORT_DATE`: 报告生成日期
- `DATA_DATE`: 数据截止日期
- `CURRENT_PRICE`: 当前股价
- `MARKET_CAP`: 总市值（格式化字符串）

### 2. 综合评分
- `OVERALL_SCORE`: 综合评分 (0-10)
- `SCORE_COLOR`: 评分颜色 class (green/yellow/red)
- `SCORE_COLOR_HEX`: 评分颜色 hex (#3fb950/#d2991d/#f85149)
- `SCORE_PERCENT`: 评分百分比
- `RATING`: 评级文字
- `RATING_COLOR`: 评级颜色
- `ONE_LINER`: 一句话结论
- `CORE_STRENGTHS`: 核心优势（HTML 文本）
- `CORE_RISKS`: 核心风险（HTML 文本）

### 3. 分析模块内容（HTML 片段）
- `QUALITY_SCREEN_CONTENT`: 质量筛选完整 HTML
- `MOAT_ANALYSIS_CONTENT`: 护城河分析完整 HTML
- `SAFETY_MARGIN_CONTENT`: 安全边际完整 HTML
- `PRICE_RANGE_SECTION`: 买入价格区间 HTML（如不适用则清空）

### 4. 图表数据
- `TREND_YEARS`: JSON 数组 `["2021","2022","2023","2024","2025"]`
- `TREND_REVENUE`: JSON 数组 营收数值
- `TREND_PROFIT`: JSON 数组 净利润数值
- `TREND_ROE`: JSON 数组 ROE 百分比值
- `RADAR_LABELS`: JSON 数组 维度名称
- `RADAR_DATA`: JSON 数组 各维度得分

## 工作流程

### Step 1: 读取模板

```bash
Read templates/report-base.html
```

### Step 2: 替换模板变量

将模板中所有 `{{VARIABLE}}` 占位符替换为实际内容：

- 文本变量 → 直接替换
- HTML 内容变量（如 `{{QUALITY_SCREEN_CONTENT}}`）→ 替换为编排器提供的 HTML 片段
- JSON 数组变量（如 `{{TREND_YEARS}}`）→ 替换为 JSON 字符串
- 条件块（如价格区间）→ 如果不适用，替换为空字符串

### Step 3: 处理特殊变量

**SCORE_COLOR 映射:**
- score >= 8 → `green`
- score >= 6 → `yellow`
- score >= 4 → `yellow`
- score < 4 → `red`

**SCORE_COLOR_HEX 映射:**
- score >= 8 → `#3fb950`
- score >= 6 → `#d2991d`
- score >= 4 → `#d2991d`
- score < 4 → `#f85149`

**SCORE_PERCENT**: (score / 10) × 100

**RATING 映射:**
- score >= 8 → 强烈推荐
- score >= 6 → 可以买入
- score >= 4 → 继续观察
- score < 4 → 回避

**RATING_COLOR**: 同 SCORE_COLOR

### Step 4: 写入报告文件

```bash
Write reports/<STOCK_CODE>-<YYYY-MM-DD>.html
```

### Step 5: 验证

- 确认文件不为空
- 确认关键占位符已全部替换（没有残留的 `{{...}}`）
- 确认 JS 数据部分语法正确（JSON 数组格式）

## 输出格式

生成报告后，告知用户：

```markdown
✅ **投资分析报告已生成**

📄 **文件**: `reports/<STOCK_CODE>-<YYYY-MM-DD>.html`
📊 **公司**: <STOCK_NAME> (<STOCK_CODE>)
🏆 **评级**: <RATING> (<OVERALL_SCORE>/10)

直接在浏览器中打开该文件即可查看交互式报告。
```

## 注意事项

- 所有 HTML 片段中的特殊字符不要二次转义
- JSON 数组输出时确保使用标准 JSON 格式（双引号）
- 价格区间不适用时，`{{PRICE_RANGE_SECTION}}` 替换为空字符串 `""`
- 报告文件名格式: `股票代码-YYYY-MM-DD.html`（如 `600519-2026-07-10.html`）
```

---

### Task 9: 创建 munger-orchestrator.md — 编排器 Skill

**文件:**
- Create: `skills/munger-orchestrator.md`

- [ ] **Step 1: 创建 Skill 文件**

```markdown
---
name: munger-orchestrator
description: 查理芒格投资分析编排器 — 混合模式对话管理、5 阶段分析工作流、综合评分汇总、驱动报告生成
---

# 查理芒格投资分析编排器

你是查理·芒格风格的投研助手编排器。你管理用户与 Agent 的对话，在自由问答和深度分析之间切换。当进入深度分析模式时，你驱动一个 5 阶段工作流。

## 角色定位

你是查理·芒格在投资分析中的化身。你的表达风格应该是：
- **简洁直接** — 不废话，不修饰
- **逆向思维** — 先想什么可能出错
- **承认无知** — 不知道就说不知道
- **强调纪律** — 烂机会永远不如不投

## 两大交互模式

### 💬 模式 1: 自由对话

**触发条件**: 用户提问不涉及完整分析。例如：
- "茅台 PE 多少？"
- "600519 最近财报怎么样？"
- "帮我搜一下比亚迪的股票代码"

**行为**:
1. 判断问题意图
2. 按需调用工具（通过 `a-share-data` Skill 获取数据）
3. 简洁回答用户问题
4. 不启动分析流程

### 📊 模式 2: 深度分析

**触发条件**: 用户明确要求分析，或使用触发词。触发词包括：
- "分析一下" / "分析" / "深度研究" / "看看这家" / "帮我评估" / "研究一下"
- 用户直接说"XX 股票怎么样"
- 用户说"帮我出一份报告"

**行为**: 启动完整的 5 阶段工作流。

## 5 阶段分析工作流

### Phase 0: 意图识别

确认：
- 分析对象是行业还是个股？
- 获取股票代码（如用户只给名称，先调 search）
- 告知用户即将开始的流程概览

```markdown
🔍 **开始分析 <股票名称> (<股票代码>)**

我将按照查理芒格的分析框架，分以下步骤进行：
1. 📡 收集数据（行情+财务+估值）
2. 🔢 质量筛选（7 指标去劣）
3. 🏰 护城河分析 + 🛡️ 安全边际评估
4. 📊 生成投资报告

预计需要 3-5 分钟...
```

### Phase 1: 数据收集（并行）

调用 `a-share-data` Skill 获取三类数据（通过 Bash 并行执行）：

```bash
python tools/ashare_data.py quote <code> --json
python tools/ashare_data.py financials <code> --json --period 年报
python tools/ashare_data.py valuation <code> --json
```

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

```markdown
🚫 **质量筛选未通过**

<股票名称> 在 [具体不通过的指标] 方面不符合芒格的一流公司标准。

按照芒格的原则："我们宁愿错过十个好机会，也不在一个烂机会上浪费时间。"

如果你仍然想深入了解这家公司，我可以继续分析，但请知悉：这家公司不符合基本质量门槛。
```

### Phase 3: 并行分析

**同时**调用两个分析 Skill：
1. `moat-analysis` — 护城河分析
2. `safety-margin` — 安全边际评估

将 Phase 1-2 的数据和结论传递给这两个 Skill。

### Phase 4: 全球对标（按需触发）

仅在以下情况触发：
- 用户明确要求全球对标
- 行业内存在明显的全球龙头可对比

如触发，调用 `global-benchmark` Skill（第二批才实现，第一批跳过此阶段）。

### Phase 5: 报告生成

#### Step 5a: 计算综合评分

基于各分析 Skill 的输出计算综合评分：

| 维度 | 权重 | 得分来源 |
|------|------|---------|
| 质量筛选 | 20% | quality-screen 输出 |
| 护城河宽度 | 25% | moat-analysis 输出 |
| 安全边际 | 20% | safety-margin 输出 |
| 管理层质量 | 15% | N/A (第二批) — 暂记 5 分 |
| 逆向风险 | 10% | N/A (第二批) — 暂记 5 分 |
| 全球对标 | 10% | N/A (第二批) — 暂记 5 分 |

综合评分 = Σ(维度得分 × 权重) / 10 × 10

评级映射：
- 8-10: 强烈推荐
- 6-8: 可以买入
- 4-6: 继续观察
- < 4: 回避

#### Step 5b: 汇总所有输出

收集以下内容并组织为报告生成器需要的格式：

1. **基础信息**: 从 Phase 1 的 quote 数据中提取
2. **综合评分**: 按上述公式计算
3. **一句话结论**: 基于所有分析结果，撰写芒格风格的总结（2-3 句话）
4. **核心优势/风险**: 从各分析 Skill 中提取
5. **分析模块 HTML**: 将每个分析 Skill 的输出格式化为 HTML 片段
6. **图表数据**: 从财务数据中提取 5 年趋势数据
7. **雷达图数据**: ROE稳定性、盈利能力、财务健康、现金流质量、品牌溢价、护城河综合、安全边际

#### Step 5c: 调用报告生成器

调用 `report-generator` Skill，将汇总数据传递给该 Skill 生成 HTML 报告。

## 异常处理总则

| 场景 | 处理 |
|------|------|
| 工具脚本执行失败 | 重试 1 次，仍失败则标记 missing |
| 数据全部不可用 | 告知用户并终止 |
| 用户中途改变意图 | 优雅切换模式，保存已有分析结果 |
| 质量筛选 FAIL | 终止流程，告知原因 |
| 分析 Skill 返回内容过少 | 标注"数据有限，分析受限" |

## 交互规范

1. **进度可见**: 每个 Phase 开始时告知用户正在做什么
2. **数据透明**: 所有结论引用具体数据支撑
3. **不确定性诚实**: 不知道的事就说不知道
4. **芒格语调**: 分析结论遵循芒格的表达风格——不模棱两可，不迎合用户
5. **最终输出**: 报告生成后，在对话中给出摘要 + 报告文件路径
```

---

### Task 10: 创建 CLAUDE.md — 项目入口文件

**文件:**
- Create: `CLAUDE.md`

- [ ] **Step 1: 创建项目入口文件**

```markdown
# AI Munger — 查理芒格投资分析 Agent

以查理·芒格投资哲学为核心的 AI 投资分析助手。用户通过多轮对话与 Agent 交互，Agent 驱动数据工具和分析技能，最终生成交互式 HTML 投资分析报告。

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
```

---

### Task 11: 端到端验证

**验证目标**: 用真实 A 股走通完整流程。

- [ ] **Step 1: 验证工具层**

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py quote 600519 --json 2>&1 | head -20
```
Expected: 贵州茅台的结构化 JSON 行情数据。

```bash
cd D:/HL/ai-munger && python tools/ashare_data.py financials 000858 --json --period 年报 2>&1 | head -30
```
Expected: 五粮液的近 5 年财务 JSON。

- [ ] **Step 2: 验证数据层**

在 Claude Code 对话中触发：
```
用 a-share-data 获取 600519 的行情、财务和估值数据
```
Expected: Agent 通过 Bash 并行执行 3 个命令，返回完整 JSON。

- [ ] **Step 3: 验证分析层**

在 Claude Code 对话中分别触发：
```
对 600519 执行 quality-screen 分析
```
Expected: 7 指标得分卡 + PASS/FAIL/CAUTION 判定。

```
对 600519 执行 moat-analysis 分析
```
Expected: 5 维度护城河评估。

```
对 600519 执行 safety-margin 分析
```
Expected: DCF/PE 估值 + 三档买入价格区间。

- [ ] **Step 4: 验证端到端流程**

```
分析一下贵州茅台
```
Expected: 完整的 5 阶段工作流执行，生成 HTML 报告在 `reports/` 目录。

- [ ] **Step 5: 验证报告质量**

在浏览器中打开生成的 HTML 报告：
- ✅ 侧栏导航可点击跳转
- ✅ 图表正常渲染（雷达图 + 趋势折线图）
- ✅ 评分条颜色正确
- ✅ 价格区间三档卡片展示正常
- ✅ 可折叠面板可展开/收起
- ✅ 免责声明出现在页脚
- ✅ 无 JS 控制台报错
- ✅ 无残留的 `{{...}}` 占位符

---

## 实施顺序

按依赖关系排列（必须串行执行的任务标注）：

| 顺序 | Task | 依赖 | 说明 |
|------|------|------|------|
| 1 | Task 1 | — | 工具层改进（基础依赖） |
| 2 | Task 2 | Task 1 | 数据 Skill（依赖工具 JSON 输出） |
| 3 | Task 3 | Task 2 | 财务验证 Skill（依赖数据 Skill） |
| 4 | Task 4 | Task 2, 3 | 质量筛选 Skill |
| 5 | Task 5 | Task 2, 3 | 护城河 Skill |
| 6 | Task 6 | Task 2, 3 | 安全边际 Skill |
| 7 | Task 7 | — | HTML 模板（独立，可与其他并行） |
| 8 | Task 8 | Task 7 | 报告生成 Skill（依赖模板） |
| 9 | Task 9 | Task 2-8 | 编排器（依赖所有下层） |
| 10 | Task 10 | Task 2-9 | CLAUDE.md（依赖所有 Skills 就绪） |
| 11 | Task 11 | Task 1-10 | 端到端验证 |

Tasks 1-3 必须串行。Tasks 4-6 可并行。Task 7 可与 4-6 并行。Task 8 依赖 7。Task 9 依赖 2-8。Task 10 依赖 2-9。

---

*Plan generated by writing-plans skill*
