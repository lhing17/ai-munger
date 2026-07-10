# AI Munger 第二批实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐分析深度——新建 3 个工具脚本 + 3 个分析 Skill + 修改 4 个现有文件，使综合评分从 3/6 维度占位变为 6/6 完整覆盖。

**Architecture:** 自底向上。3 个工具脚本可并行开发（Tasks 1-3），然后新建 3 个分析 Skill（Tasks 4-6：management-check 依赖 Task 2，global-benchmark 依赖 Task 1，inversion-test 无依赖），最后修改 4 个现有文件（Tasks 7-10）。

**Tech Stack:** Python 3 stdlib（personnel_data / industry_data）、yfinance（global_data）、Claude Code Skills / Markdown（技能层）、HTML

**总文件数:** 6 新建 + 4 修改 = 10

---

## 文件清单

| # | 文件 | 操作 | 职责 |
|---|------|------|------|
| 1 | `tools/global_data.py` | 新建 | yfinance 全球股票数据 CLI（~300 行） |
| 2 | `tools/personnel_data.py` | 新建 | 高管/股东/质押数据 CLI（~250 行） |
| 3 | `tools/industry_data.py` | 新建 | 行业均值/排名 CLI（~150 行） |
| 4 | `skills/management-check.md` | 新建 | 5 维度管理层审查 Skill |
| 5 | `skills/inversion-test.md` | 新建 | 5 类逆向风险验证 Skill |
| 6 | `skills/global-benchmark.md` | 新建 | 全球龙头对标分析 Skill |
| 7 | `skills/munger-orchestrator.md` | 修改 | Phase 1/3/4 + 评分表 |
| 8 | `templates/report-base.html` | 修改 | 3 个新 section 占位符 |
| 9 | `skills/report-generator.md` | 修改 | 3 个新变量映射 |
| 10 | `CLAUDE.md` | 修改 | Skills 和工具索引 |

---

### Task 1: 创建 tools/global_data.py — 全球股票数据 CLI

**Files:**
- Create: `tools/global_data.py`
- Prerequisite: `pip install yfinance`

- [ ] **Step 1: 安装 yfinance**

```bash
pip install yfinance
```

- [ ] **Step 2: 创建 global_data.py**

Write `D:/HL/ai-munger/tools/global_data.py`:

```python
#!/usr/bin/env python3
"""全球股票数据工具 — Yahoo Finance 数据获取，统一 JSON 输出。

为 Claude Code Skills 提供全球对标数据。
需要: pip install yfinance

用法:
    python tools/global_data.py AAPL --json
    python tools/global_data.py AAPL MSFT GOOGL --json
    python tools/global_data.py TSM --json --financials
"""

import argparse
import json
import sys

import yfinance as yf


def _safe_num(val):
    """安全转换 numpy/None 为普通 Python 类型。"""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return round(f, 2)
    except (ValueError, TypeError):
        return str(val)


def _cagr(values, years=3):
    """计算 CAGR。"""
    valid = [v for v in values if v is not None and v > 0]
    if len(valid) < years + 1:
        return None
    start, end = valid[0], valid[-1]
    if start <= 0:
        return None
    return round((end / start) ** (1 / (len(valid) - 1)) - 1, 4) * 100


def get_quote(ticker):
    """获取报价快照。"""
    try:
        info = ticker.info
        return {
            "price": _safe_num(info.get("currentPrice") or info.get("regularMarketPrice")),
            "market_cap": _safe_num(info.get("marketCap")),
            "pe_ttm": _safe_num(info.get("trailingPE")),
            "pb": _safe_num(info.get("priceToBook")),
            "52w_high": _safe_num(info.get("fiftyTwoWeekHigh")),
            "52w_low": _safe_num(info.get("fiftyTwoWeekLow")),
        }
    except Exception as e:
        return {"error": str(e)}


def get_financials(ticker):
    """获取近 5 年财务数据。"""
    try:
        # Annual financials
        fin = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        # Sort columns by date descending, take last 5
        cols = sorted(fin.columns, reverse=True)[:5]
        years = [str(c.year) for c in reversed(cols)]

        def _extract(data, fields):
            result = []
            for c in reversed(cols):
                val = None
                for f in fields:
                    if f in data.index and c in data.columns:
                        v = data.loc[f, c]
                        if v is not None and v == v and abs(v) > 0:
                            val = v
                            break
                result.append(_safe_num(val))
            return result

        revenue = _extract(fin, ["Total Revenue", "Revenue"])
        net_income = _extract(fin, ["Net Income", "Net Income Common Stockholders"])
        gross_profit = _extract(fin, ["Gross Profit"])
        r_and_d = _extract(fin, ["Research And Development", "Research & Development"])
        fcf_list = _extract(cf, ["Free Cash Flow"])

        # ROE: net_income / total_equity
        equity = _extract(bs, ["Total Equity Gross Minority Interest", "Stockholders Equity"])
        roe = []
        for ni, eq in zip(net_income, equity):
            if ni and eq and eq != 0:
                roe.append(round(ni / eq * 100, 2))
            else:
                roe.append(None)

        # Gross margin
        gross_margin = []
        for gp, rev in zip(gross_profit, revenue):
            if gp and rev and rev != 0:
                gross_margin.append(round(gp / rev * 100, 2))
            else:
                gross_margin.append(None)

        # R&D %
        r_and_d_pct = []
        for rd, rev in zip(r_and_d, revenue):
            if rd and rev and rev != 0:
                r_and_d_pct.append(round(rd / rev * 100, 2))
            else:
                r_and_d_pct.append(0.0)

        # CAGR
        rev_cagr_3 = _cagr(revenue, 3)
        rev_cagr_5 = _cagr(revenue, 5)
        # EPS
        eps = _extract(fin, ["Diluted EPS", "Basic EPS"])
        eps_cagr_3 = _cagr(eps, 3)
        eps_cagr_5 = _cagr(eps, 5)

        # Dividend
        info = ticker.info
        div_yield = _safe_num(info.get("dividendYield"))
        payout = _safe_num(info.get("payoutRatio"))

        return {
            "years": years,
            "revenue": revenue,
            "net_income": net_income,
            "roe": roe,
            "gross_margin": gross_margin,
            "r_and_d_pct": r_and_d_pct,
            "fcf": fcf_list,
        }, {
            "revenue_cagr_3y": rev_cagr_3,
            "revenue_cagr_5y": rev_cagr_5,
            "eps_cagr_3y": eps_cagr_3,
            "eps_cagr_5y": eps_cagr_5,
        }, {
            "yield": div_yield,
            "payout_ratio": payout,
        }
    except Exception as e:
        return {"error": str(e)}, {"error": str(e)}, {"error": str(e)}


def cmd_single(ticker: str):
    """获取单只股票完整数据，返回纯文本输出用的结构（非 JSON 打印版）。"""
    t = yf.Ticker(ticker)
    name = t.info.get("longName") or t.info.get("shortName") or ticker
    quote = get_quote(t)
    financials, growth, dividend = get_financials(t)
    return {
        "ticker": ticker.upper(),
        "name": name,
        "quote": quote,
        "financials": financials,
        "growth": growth,
        "dividend": dividend,
    }


def main():
    parser = argparse.ArgumentParser(
        description="全球股票数据工具 — Yahoo Finance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tickers", nargs="+", help="股票代码，如 AAPL 或 AAPL MSFT GOOGL")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--financials", action="store_true", help="仅输出财务数据")

    args = parser.parse_args()

    results = []
    for code in args.tickers:
        try:
            data = cmd_single(code.strip())
            results.append(data)
        except Exception as e:
            results.append({"ticker": code.upper(), "error": str(e)})

    if args.json:
        output = results if len(results) > 1 else results[0]
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            if "error" in r:
                print(f"[ERROR] {r['ticker']}: {r['error']}")
                continue
            print("=" * 60)
            print(f"全球对标: {r['name']} ({r['ticker']})")
            print("=" * 60)
            q = r.get("quote", {})
            print(f"  当前价:     {q.get('price', '-')}")
            print(f"  总市值:     {q.get('market_cap', '-')}")
            print(f"  PE(TTM):    {q.get('pe_ttm', '-')}")
            print(f"  PB:         {q.get('pb', '-')}")
            if not args.financials:
                fin = r.get("financials", {})
                if isinstance(fin, dict) and "years" in fin:
                    print(f"\n  财务年度:   {fin['years']}")
                    print(f"  营收:       {fin.get('revenue', '-')}")
                    print(f"  净利润:     {fin.get('net_income', '-')}")
                    print(f"  ROE:        {fin.get('roe', '-')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 验证工具脚本**

```bash
cd D:/HL/ai-munger && python tools/global_data.py AAPL --json 2>&1 | head -30
```
Expected: 返回 Apple 的结构化 JSON 数据。

```bash
cd D:/HL/ai-munger && python tools/global_data.py 0700.HK --json 2>&1 | head -20
```
Expected: 腾讯控股数据（验证港股支持）。

- [ ] **Step 4: Commit**

```bash
cd D:/HL/ai-munger && git add tools/global_data.py && git commit -m "feat: add global_data.py — Yahoo Finance global stock data CLI"
```

---

### Task 2: 创建 tools/personnel_data.py — 管理层/股东数据 CLI

**Files:**
- Create: `tools/personnel_data.py`

- [ ] **Step 1: 创建 personnel_data.py**

Write `D:/HL/ai-munger/tools/personnel_data.py`:

```python
#!/usr/bin/env python3
"""A股管理层/股东数据工具 — 东方财富 API，零外部依赖。

为 management-check Skill 提供高管履历、股东结构、质押、分红数据。

用法:
    python tools/personnel_data.py full 600519 --json
    python tools/personnel_data.py executives 600519 --json
    python tools/personnel_data.py shareholders 600519 --json
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

_TIMEOUT = 15


def _fetch(url):
    """urllib GET，返回文本。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))


def _clean_code(code: str) -> str:
    code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    return code


def _market(code: str) -> str:
    code = _clean_code(code)
    if code.startswith(("6", "9", "5")):
        return "SH"
    return "SZ"


def cmd_executives(code: str) -> dict:
    """高管信息。"""
    code_clean = _clean_code(code)
    market_cd = _market(code)
    secucode = f"{code_clean}.{market_cd}"

    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_ORG_MANAGERS",
        "sty": "ALL",
        "filter": f'(SECUCODE="{secucode}")',
        "p": "1",
        "ps": "20",
        "sr": "1",
        "st": "ORDER_NUM",
        "source": "HSF10",
        "client": "PC",
    }
    try:
        data = _fetch_json(url, params)
        rows = data.get("result", {}).get("data", [])
    except Exception as e:
        print(f"[WARN] 高管数据获取失败: {e}", file=sys.stderr)
        return []

    result = []
    for r in rows:
        result.append({
            "name": r.get("NAME", ""),
            "title": r.get("POSITION", ""),
            "start_date": str(r.get("WORK_START_DATE", ""))[:10],
            "salary": r.get("SALARY"),
            "shares_held": r.get("HOLD_NUM"),
        })
    return result


def cmd_shareholders(code: str) -> dict:
    """前十大股东 + 质押信息。"""
    code_clean = _clean_code(code)
    market_cd = _market(code)
    secucode = f"{code_clean}.{market_cd}"

    # Top 10 shareholders
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_SHAREHOLDER_TOPTEN",
        "sty": "ALL",
        "filter": f'(SECUCODE="{secucode}")',
        "p": "1",
        "ps": "10",
        "sr": "1",
        "st": "HOLD_NUM",
        "source": "HSF10",
        "client": "PC",
    }

    top10 = []
    pledge_ratio = None
    controlling = ""
    inst_holding = None

    try:
        data = _fetch_json(url, params)
        rows = data.get("result", {}).get("data", [])
        for r in rows:
            name = r.get("HOLDER_NAME", "")
            pct = r.get("HOLD_PCT")
            stype = r.get("HOLDER_TYPE", "")
            top10.append({
                "name": name,
                "stake_pct": round(float(pct), 2) if pct else None,
                "type": stype,
            })
            # 质押比例 from the API
            pledge = r.get("PLEDGE_RATIO")
            if pledge is not None and pledge_ratio is None:
                pledge_ratio = round(float(pledge), 2)
    except Exception as e:
        print(f"[WARN] 股东数据获取失败: {e}", file=sys.stderr)

    # Actual controller
    try:
        ctrl_url = "https://datacenter.eastmoney.com/securities/api/data/get"
        ctrl_params = {
            "type": "RPT_F10_ORG_ACTUALCONTROLLER",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": "1", "ps": "1",
            "source": "HSF10", "client": "PC",
        }
        ctrl_data = _fetch_json(ctrl_url, ctrl_params)
        ctrl_rows = ctrl_data.get("result", {}).get("data", [])
        if ctrl_rows:
            controlling = ctrl_rows[0].get("CONTROLLER_NAME", "")
    except Exception:
        pass

    return {
        "top10_shareholders": top10,
        "controlling_shareholder": controlling,
        "institution_holding_pct": inst_holding,
        "pledge_ratio": pledge_ratio,
        "pledge_risk": "无质押" if (pledge_ratio is None or pledge_ratio == 0) else (
            "高风险" if pledge_ratio > 50 else ("关注" if pledge_ratio > 30 else "正常")
        ),
    }


def cmd_capital_actions(code: str) -> dict:
    """分红记录 + 股本变动。"""
    code_clean = _clean_code(code)
    market_cd = _market(code)
    secucode = f"{code_clean}.{market_cd}"

    # Dividend history
    div_url = "https://datacenter.eastmoney.com/securities/api/data/get"
    div_params = {
        "type": "RPT_F10_SHARE_BONUS",
        "sty": "ALL",
        "filter": f'(SECUCODE="{secucode}")',
        "p": "1", "ps": "5",
        "sr": "-1", "st": "REPORT_DATE",
        "source": "HSF10", "client": "PC",
    }

    dividends = []
    dilution = None
    red_flags = []

    try:
        data = _fetch_json(div_url, div_params)
        rows = data.get("result", {}).get("data", [])
        for r in rows[:5]:
            dividends.append({
                "year": str(r.get("REPORT_DATE", ""))[:4],
                "dividend_per_share": r.get("BONUS_ITEMS"),
                "ex_date": str(r.get("EX_DATE", ""))[:10],
            })
    except Exception as e:
        print(f"[WARN] 分红数据获取失败: {e}", file=sys.stderr)

    # Share count change (dilution)
    try:
        share_url = "https://datacenter.eastmoney.com/securities/api/data/get"
        share_params = {
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "TOTAL_SHARES",
            "filter": f'(SECUCODE="{secucode}")(REPORT_TYPE="年报")',
            "p": "1", "ps": "5",
            "sr": "-1", "st": "REPORT_DATE",
            "source": "HSF10", "client": "PC",
        }
        sdata = _fetch_json(share_url, share_params)
        srows = sdata.get("result", {}).get("data", [])
        shares_list = []
        for s in srows[:5]:
            ts = s.get("TOTAL_SHARES")
            if ts:
                shares_list.append(float(ts))
        if len(shares_list) >= 2:
            dilution = round(
                (shares_list[0] / shares_list[-1]) ** (1 / (len(shares_list) - 1)) - 1, 4
            ) * 100
    except Exception:
        pass

    if dilution is not None and dilution > 3:
        red_flags.append(f"股本稀释率偏高: {dilution:.1f}%/年（>3%）")

    return {
        "dividend_history_5y": dividends,
        "total_shares_dilution_5y": dilution,
        "dilution_assessment": (
            "股本稳定，无明显稀释" if dilution is None or dilution < 1 else
            f"稀释率 {dilution:.1f}%/年"
        ),
        "red_flags": red_flags,
    }


def cmd_full(code: str) -> dict:
    return {
        "code": _clean_code(code),
        "executives": cmd_executives(code),
        "ownership": cmd_shareholders(code),
        "capital_actions": cmd_capital_actions(code),
    }


def main():
    parser = argparse.ArgumentParser(
        description="A股管理层/股东数据工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_exe = sub.add_parser("executives", help="高管信息")
    p_exe.add_argument("code")

    p_sh = sub.add_parser("shareholders", help="股东信息")
    p_sh.add_argument("code")

    p_full = sub.add_parser("full", help="完整报告")
    p_full.add_argument("code")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "executives": lambda: cmd_executives(args.code),
        "shareholders": lambda: cmd_shareholders(args.code),
        "full": lambda: cmd_full(args.code),
    }

    result = cmds[args.command]()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证工具脚本**

```bash
cd D:/HL/ai-munger && python tools/personnel_data.py full 600519 --json 2>&1 | head -30
```
Expected: 返回茅台的高管列表 + 股东结构 + 分红记录的 JSON。

```bash
cd D:/HL/ai-munger && python tools/personnel_data.py executives 000858 --json 2>&1 | head -20
```
Expected: 五粮液高管 JSON。

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add tools/personnel_data.py && git commit -m "feat: add personnel_data.py — A-share management & shareholder data CLI"
```

---

### Task 3: 创建 tools/industry_data.py — 行业数据 CLI

**Files:**
- Create: `tools/industry_data.py`

- [ ] **Step 1: 创建 industry_data.py**

Write `D:/HL/ai-munger/tools/industry_data.py`:

```python
#!/usr/bin/env python3
"""A股行业数据工具 — 东方财富行业板块 API，零外部依赖。

为 moat-analysis 和 quality-screen 提供行业基准数据。

用法:
    python tools/industry_data.py 白酒 --json
    python tools/industry_data.py search 新能源 --json
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode

_TIMEOUT = 15


def _fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))


def cmd_search(keyword: str) -> list:
    """搜索行业板块。"""
    url = "https://searchadapter.eastmoney.com/api/suggest/get"
    params = {
        "input": keyword,
        "type": "15",  # 行业板块
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": "10",
    }
    try:
        data = _fetch_json(url, params)
        results = data.get("QuotationCodeTable", {}).get("Data", [])
    except Exception:
        return []

    items = []
    for r in results:
        items.append({
            "code": r.get("Code", ""),
            "name": r.get("Name", ""),
        })
    return items


def cmd_industry(name: str) -> dict:
    """获取行业板块数据。"""
    # Step 1: 搜索行业找到板块代码
    matches = cmd_search(name)
    if not matches:
        return {"error": f"未找到行业: {name}"}

    bk_code = matches[0]["code"]
    bk_name = matches[0]["name"]

    # Step 2: 获取板块成分股
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "50",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f20",  # 总市值
        "fs": f"b:{bk_code}+f:!200",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f37,f38,f39,f40,f41,f45,f46",
    }

    try:
        data = _fetch_json(url, params)
        stocks = data.get("data", {}).get("diff", [])
    except Exception as e:
        print(f"[WARN] 行业数据获取失败: {e}", file=sys.stderr)
        return {"error": f"行业数据获取失败: {e}"}

    if not stocks:
        return {"error": f"行业 {bk_name} 无成分股数据"}

    # Step 3: 计算均值
    roes, gms, nms, pes, debt_ratios, rev_growths = [], [], [], [], [], []
    top_cap, top_roe = [], []

    for s in stocks:
        roe = s.get("f37")  # ROE
        gm = s.get("f39")   # 毛利率
        nm = s.get("f40")   # 净利率
        pe = s.get("f9")    # PE
        debt = s.get("f41") # 负债率
        rev_g = s.get("f38") # 营收增速
        mcap = s.get("f20")  # 总市值
        name_s = s.get("f14", "")
        code_s = s.get("f12", "")

        for lst, val in [(roes, roe), (gms, gm), (nms, nm), (pes, pe),
                         (debt_ratios, debt), (rev_growths, rev_g)]:
            if val is not None and val != "-" and val != "":
                try:
                    lst.append(float(val))
                except (ValueError, TypeError):
                    pass

        if mcap and mcap != "-":
            try:
                top_cap.append((code_s, name_s, float(mcap) / 1e8))
            except (ValueError, TypeError):
                pass
        if roe and roe != "-":
            try:
                top_roe.append((code_s, name_s, float(roe)))
            except (ValueError, TypeError):
                pass

    def _avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    top_cap.sort(key=lambda x: x[2], reverse=True)
    top_roe.sort(key=lambda x: x[2], reverse=True)

    return {
        "industry": bk_name,
        "company_count": len(stocks),
        "averages": {
            "roe": _avg(roes),
            "gross_margin": _avg(gms),
            "net_margin": _avg(nms),
            "pe": _avg(pes),
            "debt_ratio": _avg(debt_ratios),
            "revenue_growth_3y": _avg(rev_growths),
        },
        "top_by_market_cap": [
            {"code": c, "name": n, "market_cap_yi": round(m, 0)} for c, n, m in top_cap[:5]
        ],
        "top_by_roe": [
            {"code": c, "name": n, "roe": round(r, 2)} for c, n, r in top_roe[:5]
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="A股行业数据工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_ind = sub.add_parser("industry", help="行业概况")
    p_ind.add_argument("name", help="行业名称，如 白酒")

    p_search = sub.add_parser("search", help="搜索行业")
    p_search.add_argument("keyword", help="关键词")

    args = parser.parse_args()

    # Allow calling with just positional arg (no subcommand)
    if not args.command:
        # Treat as industry lookup
        result = cmd_industry(args.name if hasattr(args, 'name') else sys.argv[1])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "search":
        result = cmd_search(args.keyword)
    elif args.command == "industry":
        result = cmd_industry(args.name)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证工具脚本**

```bash
cd D:/HL/ai-munger && python tools/industry_data.py 白酒 --json 2>&1 | head -30
```
Expected: 返回白酒行业均值 ROE/毛利率/PE 及茅台五粮液等排名 JSON。

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add tools/industry_data.py && git commit -m "feat: add industry_data.py — A-share industry benchmark CLI"
```

---

### Task 4: 创建 skills/management-check.md — 管理层审查 Skill

**Files:**
- Create: `skills/management-check.md`
- Depends on: Task 2 (personnel_data.py)

- [ ] **Step 1: 创建 Skill 文件**

Write `D:/HL/ai-munger/skills/management-check.md`:

```markdown
---
name: management-check
description: 芒格管理层审查 — 5 维度评估资本配置者的诚信与能力，输出信任等级和红旗信号
---

# 芒格管理层审查

你是查理·芒格风格的管理层审计师。芒格说："我们只投资我们信任的管理层。把钱交给不正直的人，就像把车钥匙交给醉酒的人。"

## 输入要求

需要以下数据：
- `personnel_data.py full <code> --json` 的输出（高管、股东、分红、股本变动）
- quality-screen 的财务数据（ROIC、净利润、营收）
- WebSearch 补充验证（社交媒体/新闻搜索管理层正面/负面报道）

## 5 项审查指标

### 1. 资本配置能力 💼 (权重 25%)
**规则**: ROIC/WACC 近5年均 > 1.2；大型并购（>净资产10%）无重大商誉减值
- ✅ PASS: ROIC 持续 > WACC，且无重大减值
- ⚠️ CAUTION: ROIC 偶尔 < WACC，或有1次减值
- ❌ FAIL: ROIC 持续 < WACC，或多次减值、多元化并购失败

### 2. 股权激励合理性 📊 (权重 20%)
**规则**: 近5年总股本 CAGR < 2%/年
- ✅ PASS: < 1%/年（股本稳定），股权激励有业绩条件
- ⚠️ CAUTION: 1-3%/年
- ❌ FAIL: > 3%/年（严重稀释），或激励方案过度慷慨

### 3. 分红与回购 💰 (权重 20%)
**规则**: 有利润时应有合理的股东回报
- ✅ PASS: 稳定分红（分红率 30-70%）+ 合理回购
- ⚠️ CAUTION: 不分红但将利润用于高回报再投资（需论证）
- ❌ FAIL: 有利润但不分红不回购（铁公鸡），或借钱分红

### 4. 言行一致性 🎯 (权重 20%)
**规则**: 年报承诺 vs 实际执行的差距
- ✅ PASS: 承诺基本兑现，无大额异常关联交易
- ⚠️ CAUTION: 有轻微延迟或战略调整，但方向正确
- ❌ FAIL: 承诺反复变更、"画饼"、大额异常关联交易转移利益

### 5. 大股东行为 🔒 (权重 15%)
**规则**: 大股东质押比例 < 30%；近2年无连续大额减持
- ✅ PASS: 无质押（或<10%）+ 无减持/增持
- ⚠️ CAUTION: 质押 30-50%，或偶有小额减持
- ❌ FAIL: 质押 > 50%（掏空风险），或持续大额减持

## 评分方法

PASS = 1分, CAUTION = 0.5分, FAIL = 0分 → 加权求和 × 10 = 总分 (0-10)

**信任等级映射:**
- 9-10: A（卓越 —— 可放心托付）
- 7-9: B（良好 —— 能力或诚信有一个需关注）
- 5-7: C（一般 —— 有改进空间）
- 3-5: D（存疑 —— 需要更多证据）
- < 3: F（不合格 —— 回避）

## 输出格式

```markdown
## 管理层审查: <股票名称>

**管理层信任等级: X / 总分 X.X / 10**

| # | 维度 | 结果 | 得分 | 依据 |
|---|------|------|------|------|
| 1 | 资本配置 | ✅ | 2.5 | ROIC 28% vs WACC 8%，无并购减值 |
| 2 | 股权激励 | ✅ | 2.0 | 5年股本稀释 0.1%/年 |
| 3 | 分红回购 | ✅ | 2.0 | 分红率 51%，持续增长 |
| 4 | 言行一致 | ⚠️ | 1.0 | [具体偏离] |
| 5 | 大股东行为 | ✅ | 1.5 | 0质押，0减持 |

### 🔴 红旗信号
- [无 / 列出具体风险项]

### 芒格视角
[2-3句话：会把钱交给这个人/这群人管理吗？为什么？]
```

## 注意事项

- 数据不足的维度标记"数据不足，保守估计 0 分"
- 红旗信号只要有 1 个，信任等级最高只能到 B
- 国企 vs 民企的管理层评估侧重点不同：国企看稳定性和政策执行力，民企看创始人能力和利益一致性
```

- [ ] **Step 2: 复制到 .claude/skills/**

```bash
cp D:/HL/ai-munger/skills/management-check.md D:/HL/ai-munger/.claude/skills/management-check.md
```

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add skills/management-check.md .claude/skills/management-check.md && git commit -m "feat: add management-check skill — 5-dimension management audit"
```

---

### Task 5: 创建 skills/inversion-test.md — 逆向思维验证 Skill

**Files:**
- Create: `skills/inversion-test.md`

- [ ] **Step 1: 创建 Skill 文件**

Write `D:/HL/ai-munger/skills/inversion-test.md`:

```markdown
---
name: inversion-test
description: 芒格逆向思维验证 — 主动寻找 5 类致命风险，输出风险地图和概率×影响矩阵
---

# 芒格逆向思维验证

你是查理·芒格风格的逆向风险分析师。芒格说："反过来想，总是反过来想。告诉我我会死在哪里，我就永远不去那里。"

你的角色不是一个客观分析师——你是一个**职业空头**。你的任务是用最锋利的视角找到这家公司的致命弱点。你不对任何公司有感情。

## 输入要求

- 行业/公司业务描述（来自 financial-query 的补充数据）
- 近 5 年财务数据（来自 a-share-data）
- 客户/供应商/产品/地区集中度数据
- WebSearch 搜索行业风险、政策风险、负面新闻

## 5 类风险场景

### 1. 行业颠覆 ⚡ (权重 25%)
**核心问题:** 5-10年内，什么技术或商业模式可能让这家公司过时？

评分：
- 9-10: 不可颠覆 —— 白酒文化、铁路、电力
- 6-8: 低风险 —— 有技术壁垒，替换成本高
- 3-5: 中等风险 —— 面临渐进式替代
- 1-2: 高危 —— 柯达/诺基亚级别的颠覆威胁

### 2. 监管打击 🏛️ (权重 25%)
**核心问题:** 是否面临教育双减、医疗集采、反垄断、数据安全级别的政策风险？

评分：
- 9-10: 政策友好 —— 国家鼓励的战略行业
- 6-8: 低风险 —— 成熟监管框架
- 3-5: 中等风险 —— 政策方向不确定
- 1-2: 高危 —— 已在监管打击靶心

### 3. 关键人物 👤 (权重 15%)
**核心问题:** 创始人/核心高管离职或出事的影响？

评分：
- 9-10: 制度化 —— 管理层已制度化，不依赖个人
- 6-8: 低依赖 —— 有明确的继任计划
- 3-5: 中等依赖 —— 创始人仍是精神领袖
- 1-2: 极端依赖 —— 公司=创始人，无创始人=无公司

### 4. 集中度风险 🎯 (权重 20%)
**核心问题:** 是否过度依赖单一客户/供应商/产品/地区？

规则：
- 单一客户 > 30% 营收 → 高分险
- 单一供应商 > 30% 采购 → 高分险
- 单一产品 > 50% 营收 → 关注
- 单一地区 > 70% 营收 → 关注

评分：
- 9-10: 完全分散
- 6-8: 有一定集中但不致命
- 3-5: 显著集中，值得担忧
- 1-2: 高度集中，一损俱损

### 5. 财务疑点 🔍 (权重 15%)
**核心问题:** 是否存在财务造假或盈余管理的信号？

检查信号：
- 存贷双高（货币资金和有息负债同时很高）
- 应收账款增速持续 > 营收增速
- 审计师频繁更换（3年内 > 1次）
- 关联交易占比异常
- 商誉/净资产 > 50%

评分：
- 9-10: 财报透明，无异常
- 6-8: 有小瑕疵，但无系统性风险
- 3-5: 多项疑点，需要深入调查
- 1-2: 严重怀疑财务造假

## 评分规则

每个场景 0-10 → 加权求和 → 直接映射为 inversion-test 贡献分

## 输出格式

```markdown
## 逆向风险验证: <股票名称>

**逆向安全分: X.X / 10 | 风险等级: (安全🔵/警惕🟡/危险🔴)**

### 风险地图

| 风险类型 | 概率(1-5) | 影响(1-5) | 得分 | 关键论据 |
|----------|-----------|-----------|------|---------|
| 行业颠覆 | 2 | 3 | 8 | [为什么不易被颠覆] |
| 监管打击 | 1 | 4 | 8 | [政策风险分析] |
| 关键人物 | 3 | 2 | 7 | [继任计划评估] |
| 集中度 | 1 | 2 | 9 | [客户/供应商分布] |
| 财务疑点 | 1 | 5 | 8 | [财务质量评估] |

### 最可能杀死这家公司的 3 种方式

1. **[风险场景1]**: [详细论证]
2. **[风险场景2]**: [详细论证]
3. **[风险场景3]**: [详细论证]

### 反脆弱特征

[这家公司的哪些特征让它不仅抗风险，还能从危机中获益？]
```

## 注意事项

- 不回避任何风险——即使公司看起来完美，也要找到它的弱点
- 概率和影响用 1-5 打分（1=极低，5=极高）
- 得分高 = 安全（风险小），得分低 = 危险（风险大）
```

- [ ] **Step 2: 复制到 .claude/skills/**

```bash
cp D:/HL/ai-munger/skills/inversion-test.md D:/HL/ai-munger/.claude/skills/inversion-test.md
```

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add skills/inversion-test.md .claude/skills/inversion-test.md && git commit -m "feat: add inversion-test skill — 5-category fatal risk analysis"
```

---

### Task 6: 创建 skills/global-benchmark.md — 全球龙头对标 Skill

**Files:**
- Create: `skills/global-benchmark.md`
- Depends on: Task 1 (global_data.py)

- [ ] **Step 1: 创建 Skill 文件**

Write `D:/HL/ai-munger/skills/global-benchmark.md`:

```markdown
---
name: global-benchmark
description: 芒格全球龙头对标 — 与全球最好的公司对比，分析差距在哪里、为什么、能否追上
---

# 芒格全球龙头对标

你是查理·芒格风格的全球对标分析师。芒格说："理解一家公司最好的方式之一是跟全球最好的对手比——差距在哪里，为什么。"

## 输入要求

- A 股目标公司数据（来自 a-share-data: quote + financials）
- 行业数据（来自 industry_data.py）
- 全球对标公司数据（来自 global_data.py）
- 编排器通过常识 + WebSearch 确定对标对象

## 对标对象确定

编排器在调用你之前会：
1. 从 industry_data 获取行业信息
2. 通过常识 + WebSearch 确定 1-3 个全球龙头
3. 调用 global_data.py 获取对标公司数据

## 不可对标的情况

如果行业无全球可比龙头（如白酒），直接返回：

```markdown
## 全球对标: 不适用

**该行业在全球范围内无直接可比上市公司。**
[简短解释原因]。该维度不计入综合评分。
```

## 5 个对标维度

### 1. 盈利能力对比 📊 (权重 30%)
对比 ROE / 毛利率 / 净利率
- A 股 vs 全球龙头，差距 < 5pp → 9-10分
- 差距 5-15pp → 6-8分
- 差距 > 15pp → 1-5分

### 2. 估值对比 💎 (权重 20%)
对比 PE / PB / PS
- A 股被显著低估 → 高分
- 估值相当 → 中等
- 显著溢价 → 低分
- 注意：低估值可能反映质量差距

### 3. 成长性对比 🚀 (权重 20%)
对比近 3 年营收/利润 CAGR
- A 股增速 > 全球龙头 → 有望缩小差距 → 高分
- 增速相当 → 中等
- 增速落后 → 差距在扩大 → 低分

### 4. 研发与国际化 🌐 (权重 15%)
对比研发费率和海外营收占比
- 差距越大 → "天花板"越高 → 但短期内难以赶超

### 5. 市值差距 📏 (权重 15%)
分析绝对市值差距是"合理的规模折价"还是"低估的成长空间"

## 输出格式

```markdown
## 全球龙头对标: <A股公司> vs <全球龙头>

### 关键指标对比

| 指标 | <A股公司> | <全球龙头1> | <全球龙头2> |
|------|----------|------------|------------|
| ROE | 32.5% | 172% | 85% |
| 毛利率 | 92.1% | 46.2% | 54.3% |
| PE(TTM) | 17.9 | 35.2 | 28.1 |
| 营收CAGR 3Y | 5.2% | 0.7% | 8.3% |
| 研发费率 | 0.1% | 7.8% | 6.5% |
| 海外营收占比 | 3% | 65% | 58% |
| 市值(亿USD) | 2,060 | 37,500 | 31,000 |

### 对标评分

| 维度 | 得分 | 权重 | 加权 | 判断 |
|------|------|------|------|------|
| 盈利能力 | 9 | 30% | 2.7 | ROE和毛利率远超全球龙头 |
| 估值 | 8 | 20% | 1.6 | 明显低于全球龙头估值 |
| 成长性 | 7 | 20% | 1.4 | 增速高于 Apple，但低于预期 |
| 研发/国际化 | 2 | 15% | 0.3 | 研发投入和国际化几乎为零 |
| 市值差距 | 4 | 15% | 0.6 | 市值差距 18 倍，有空间但路途遥远 |

**总分: 6.6 / 10**

### 差距清单

- ✅ 已超越: [列出]
- 🔄 正在追赶: [列出]
- ❌ 差距巨大: [列出]

### 芒格视角

[2-3句话：这些差距是护城河的反映还是成长空间？]
```

## 注意事项

- 对标不是评判谁"更好"，而是分析差距的本质——是模式差异、阶段差异还是质量差异
- 无对标物时不强凑，返回"不适用"
- 估值对比要加上上下文：茅台 PE 低于可口可乐，可能反映成长性、政策风险或市场结构差异
```

- [ ] **Step 2: 复制到 .claude/skills/**

```bash
cp D:/HL/ai-munger/skills/global-benchmark.md D:/HL/ai-munger/.claude/skills/global-benchmark.md
```

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add skills/global-benchmark.md .claude/skills/global-benchmark.md && git commit -m "feat: add global-benchmark skill — global leader comparison analysis"
```

---

### Task 7: 修改 skills/munger-orchestrator.md

**Files:**
- Modify: `skills/munger-orchestrator.md`

- [ ] **Step 1: 更新 Phase 0 流程概览**

Edit the Phase 0 section (line 51-61) to mention 6 analysis dimensions instead of 2:

Find the text:
```
1. 📡 收集数据（行情+财务+估值）
2. 🔢 质量筛选（7 指标去劣）
3. 🏰 护城河分析 + 🛡️ 安全边际评估
4. 📊 生成投资报告
```

Replace with:
```
1. 📡 收集数据（行情+财务+估值+管理层+行业）
2. 🔢 质量筛选（7 指标去劣）
3. 🧠 四路分析（护城河 + 安全边际 + 管理层 + 逆向验证）
4. 🌍 全球龙头对标
5. 📊 生成投资报告
```

- [ ] **Step 2: 更新 Phase 1 数据收集（5 路并行）**

Find the text (lines 63-71):
```
调用 `a-share-data` Skill 获取三类数据（通过 Bash 并行执行）：

```bash
python tools/ashare_data.py quote <code> --json
python tools/ashare_data.py financials <code> --json --period 年报
python tools/ashare_data.py valuation <code> --json
```
```

Replace with:
```
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
```

- [ ] **Step 3: 更新 Phase 3（4 路并行）**

Find the text (lines 101-107):
```
### Phase 3: 并行分析

**同时**调用两个分析 Skill：
1. `moat-analysis` — 护城河分析
2. `safety-margin` — 安全边际评估

将 Phase 1-2 的数据和结论传递给这两个 Skill。
```

Replace with:
```
### Phase 3: 并行分析

**同时**调用 4 个分析 Skill：
1. `moat-analysis` — 护城河分析
2. `safety-margin` — 安全边际评估
3. `management-check` — 管理层审查（新）
4. `inversion-test` — 逆向风险验证（新）

将 Phase 1-2 的数据和结论传递给这 4 个 Skill。moat-analysis 可使用 industry_data 的行业均值做对标。
```

- [ ] **Step 4: 更新 Phase 4（激活）**

Find the text (lines 109-115):
```
### Phase 4: 全球对标（按需触发）

仅在以下情况触发：
- 用户明确要求全球对标
- 行业内存在明显的全球龙头可对比

如触发，调用 `global-benchmark` Skill（第二批才实现，第一批跳过此阶段）。
```

Replace with:
```
### Phase 4: 全球对标（按需触发）

触发条件：
- 通过 WebSearch 或常识判断该行业存在全球可比龙头
- 用户明确要求全球对标
- 典型可对标行业：消费（可口可乐vs茅台）、科技（台积电vs中芯）、汽车（丰田vs比亚迪）、医药（辉瑞vs恒瑞）、制造（卡特彼勒vs三一）
- 通常不触发：中国独有行业（白酒、中药）、强政策管制行业（军工）

**触发时：**
1. 通过 WebSearch + 常识确定 1-3 个全球龙头股票代码
2. 调用 `global_data.py` 获取对标数据
3. 将 A 股数据 + 对标数据传递给 `global-benchmark` Skill

**不触发时：**
- 跳过该 Phase
- 在 Phase 5 综合评分中 global-benchmark 权重归零，其余 5 维度按比例重分配（÷0.9）
```

- [ ] **Step 5: 更新 Phase 5 评分表**

Find the table (lines 123-130):
```
| 维度 | 权重 | 得分来源 |
|------|------|---------|
| 质量筛选 | 20% | quality-screen 输出 |
| 护城河宽度 | 25% | moat-analysis 输出 |
| 安全边际 | 20% | safety-margin 输出 |
| 管理层质量 | 15% | N/A (第二批) — 暂记 5 分 |
| 逆向风险 | 10% | N/A (第二批) — 暂记 5 分 |
| 全球对标 | 10% | N/A (第二批) — 暂记 5 分 |
```

Replace with:
```
| 维度 | 权重 | 得分来源 |
|------|------|---------|
| 质量筛选 | 20% | quality-screen |
| 护城河宽度 | 25% | moat-analysis |
| 安全边际 | 20% | safety-margin |
| 管理层质量 | 15% | management-check |
| 逆向风险 | 10% | inversion-test |
| 全球对标 | 10% | global-benchmark |

**特殊情况:** global-benchmark 返回"不适用"时 → 权重归零，其余 5 维度按 ÷0.9 重分配权重。

**评分计算:** 综合评分 = Σ(维度得分 × 权重) ÷ 10 × 10
```

- [ ] **Step 6: 更新 Step 5b 汇总列表**

Find the line 148-150 (分析模块 HTML):
Update to mention the 3 new modules:

Add after line 150 (after "7. **雷达图数据**: ..."):
```
8. **管理层 HTML**: management-check 输出
9. **逆向风险 HTML**: inversion-test 输出
10. **全球对标 HTML**: global-benchmark 输出（不适用时省略）
```

- [ ] **Step 7: 同步 .claude/skills/ 并提交**

```bash
cp D:/HL/ai-munger/skills/munger-orchestrator.md D:/HL/ai-munger/.claude/skills/munger-orchestrator.md
cd D:/HL/ai-munger && git add skills/munger-orchestrator.md .claude/skills/munger-orchestrator.md && git commit -m "feat: update orchestrator — 6-dimension scoring, 4 parallel analysis, activate Phase 4"
```

---

### Task 8: 修改 templates/report-base.html — 新增 3 个 section

**Files:**
- Modify: `templates/report-base.html`

- [ ] **Step 1: 新增侧栏导航项**

Find (line 320-321):
```html
  <a href="#safety">🛡️ 安全边际</a>
  <a href="#charts">📈 关键图表</a>
```

Replace with:
```html
  <a href="#safety">🛡️ 安全边际</a>
  <a href="#management">👔 管理层审查</a>
  <a href="#inversion">🪞 逆向风险</a>
  <a href="#benchmark">🌍 全球对标</a>
  <a href="#charts">📈 关键图表</a>
```

- [ ] **Step 2: 新增 3 个内容 section**

Find (line 398-399):
```html
    {{PRICE_RANGE_SECTION}}
  </section>
```

After `</section>` (which closes section#safety), insert:

```html

  <section id="management" class="section">
    <h2>👔 管理层审查</h2>
    <p class="subtitle">5 维度评估资本配置者 — "把钱交给值得信任的人"</p>
    {{MANAGEMENT_CHECK_CONTENT}}
  </section>

  <section id="inversion" class="section">
    <h2>🪞 逆向风险验证</h2>
    <p class="subtitle">主动寻找致命风险 — "告诉我我会死在哪里"</p>
    {{INVERSION_TEST_CONTENT}}
  </section>

  <section id="benchmark" class="section">
    <h2>🌍 全球龙头对标</h2>
    <p class="subtitle">与全球最好的对手比 — "差距在哪里，为什么"</p>
    {{GLOBAL_BENCHMARK_CONTENT}}
  </section>
```

- [ ] **Step 3: Commit**

```bash
cd D:/HL/ai-munger && git add templates/report-base.html && git commit -m "feat: add 3 new report sections — management, inversion, global benchmark"
```

---

### Task 9: 修改 skills/report-generator.md — 新增 3 个变量

**Files:**
- Modify: `skills/report-generator.md`

- [ ] **Step 1: 新增变量到输入要求**

Find (line 34-37):
```markdown
- `SAFETY_MARGIN_CONTENT`: 安全边际完整 HTML
- `PRICE_RANGE_SECTION`: 买入价格区间 HTML（如不适用则传空字符串）
```

Replace with:
```markdown
- `SAFETY_MARGIN_CONTENT`: 安全边际完整 HTML
- `PRICE_RANGE_SECTION`: 买入价格区间 HTML（如不适用则传空字符串）
- `MANAGEMENT_CHECK_CONTENT`: 管理层审查完整 HTML
- `INVERSION_TEST_CONTENT`: 逆向风险验证完整 HTML
- `GLOBAL_BENCHMARK_CONTENT`: 全球对标完整 HTML（不适用时传空字符串）
```

- [ ] **Step 2: 更新替换规则说明**

Find (line 58):
```markdown
- **HTML 内容变量**（`QUALITY_SCREEN_CONTENT`, `MOAT_ANALYSIS_CONTENT`, `SAFETY_MARGIN_CONTENT`, `PRICE_RANGE_SECTION`）→ 替换为编排器传入的 HTML 片段
```

Replace with:
```markdown
- **HTML 内容变量**（`QUALITY_SCREEN_CONTENT`, `MOAT_ANALYSIS_CONTENT`, `SAFETY_MARGIN_CONTENT`, `PRICE_RANGE_SECTION`, `MANAGEMENT_CHECK_CONTENT`, `INVERSION_TEST_CONTENT`, `GLOBAL_BENCHMARK_CONTENT`）→ 替换为编排器传入的 HTML 片段。global-benchmark 不适用时传空字符串 `""`
```

- [ ] **Step 3: 同步 .claude/skills/ 并提交**

```bash
cp D:/HL/ai-munger/skills/report-generator.md D:/HL/ai-munger/.claude/skills/report-generator.md
cd D:/HL/ai-munger && git add skills/report-generator.md .claude/skills/report-generator.md && git commit -m "feat: update report-generator — support 3 new content variables"
```

---

### Task 10: 修改 CLAUDE.md — 更新索引

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 Skills 表**

Find the table (lines 38-46):
```
| `munger-orchestrator` | 🎯 总编排 | 用户启动深度分析时 |
| `a-share-data` | 📡 A 股数据获取 | ... |
| `financial-query` | 📡 财务交叉验证 | ... |
| `quality-screen` | 🧠 质量筛选 | ... |
| `moat-analysis` | 🧠 护城河分析 | ... |
| `safety-margin` | 🧠 安全边际评估 | ... |
| `report-generator` | 📄 报告生成 | ... |
```

Replace with:
```markdown
| `munger-orchestrator` | 🎯 总编排 | 用户启动深度分析时 |
| `a-share-data` | 📡 A 股数据获取 | 需要行情/财务/估值数据时 |
| `financial-query` | 📡 财务交叉验证 | 数据需要验证时 |
| `quality-screen` | 🧠 质量筛选 | 分析流程 Phase 2 |
| `moat-analysis` | 🧠 护城河分析 | 分析流程 Phase 3 |
| `safety-margin` | 🧠 安全边际评估 | 分析流程 Phase 3 |
| `management-check` | 🧠 管理层审查 | 分析流程 Phase 3 |
| `inversion-test` | 🧠 逆向风险验证 | 分析流程 Phase 3 |
| `global-benchmark` | 🧠 全球龙头对标 | 分析流程 Phase 4 |
| `report-generator` | 📄 报告生成 | 分析流程 Phase 5 |
```

- [ ] **Step 2: 更新深度分析流程描述**

Find (line 34):
```
深度分析流程：数据收集 → 质量筛选 → 护城河分析 + 安全边际 → HTML 报告
```

Replace with:
```
深度分析流程：数据收集 → 质量筛选 → 四路并行分析（护城河+安全边际+管理层+逆向风险）→ 全球对标 → HTML 报告
```

- [ ] **Step 3: 新增 3 个工具脚本命令**

Find (lines 63-64):
```bash
# 搜索股票
python tools/ashare_data.py search 茅台 --json
```

After this, add:
```bash
# 全球对标数据
python tools/global_data.py AAPL --json

# 管理层/股东数据
python tools/personnel_data.py full 600519 --json

# 行业数据
python tools/industry_data.py 白酒 --json
```

- [ ] **Step 4: Commit**

```bash
cd D:/HL/ai-munger && git add CLAUDE.md && git commit -m "feat: update CLAUDE.md — index new 3 skills and 3 tools"
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 验证所有工具脚本**

```bash
cd D:/HL/ai-munger && python tools/global_data.py AAPL --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','FAIL'))"
```
Expected: `Apple Inc.`

```bash
cd D:/HL/ai-munger && python tools/personnel_data.py full 600519 --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('code','FAIL'))"
```
Expected: `600519`

```bash
cd D:/HL/ai-munger && python tools/industry_data.py 白酒 --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('industry','FAIL'))"
```
Expected: 行业名称

- [ ] **Step 2: 验证 Skills 文件就位**

```bash
cd D:/HL/ai-munger && ls -la skills/management-check.md skills/inversion-test.md skills/global-benchmark.md .claude/skills/management-check.md .claude/skills/inversion-test.md .claude/skills/global-benchmark.md
```
Expected: 6 files found.

- [ ] **Step 3: 验证模板新增占位符**

```bash
cd D:/HL/ai-munger && grep -c "MANAGEMENT_CHECK_CONTENT\|INVERSION_TEST_CONTENT\|GLOBAL_BENCHMARK_CONTENT" templates/report-base.html
```
Expected: `3`

- [ ] **Step 4: 验证 orchestrator 更新**

```bash
cd D:/HL/ai-munger && grep -c "management-check\|inversion-test\|global-benchmark" skills/munger-orchestrator.md
```
Expected: >= 5 (每个 Skill 被引用 1-2 次)

---

## 实施顺序

| 顺序 | Task | 依赖 | 可并行 |
|------|------|------|--------|
| 1 | Task 1: global_data.py | pip install yfinance | ✅ 与 2,3 并行 |
| 2 | Task 2: personnel_data.py | — | ✅ 与 1,3 并行 |
| 3 | Task 3: industry_data.py | — | ✅ 与 1,2 并行 |
| 4 | Task 4: management-check.md | Task 2 | ✅ 与 5,6 并行 |
| 5 | Task 5: inversion-test.md | — | ✅ 与 4,6 并行 |
| 6 | Task 6: global-benchmark.md | Task 1 | ✅ 与 4,5 并行 |
| 7 | Task 7: orchestrator 修改 | Tasks 4-6 | 串行 |
| 8 | Task 8: report-base.html 修改 | — | ✅ 与 9,10 并行 |
| 9 | Task 9: report-generator 修改 | — | ✅ 与 8,10 并行 |
| 10 | Task 10: CLAUDE.md 修改 | — | ✅ 与 8,9 并行 |
| 11 | Task 11: E2E 验证 | Tasks 1-10 | 串行（最后） |

---
