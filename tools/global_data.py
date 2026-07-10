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
        return None


def _cagr(values, years=3):
    """计算 CAGR。"""
    valid = [v for v in values if v is not None and isinstance(v, (int, float)) and v > 0]
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
        fin = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow

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

        equity = _extract(bs, ["Total Equity Gross Minority Interest", "Stockholders Equity"])
        roe = []
        for ni, eq in zip(net_income, equity):
            if ni is not None and eq is not None and eq != 0:
                roe.append(round(ni / eq * 100, 2))
            else:
                roe.append(None)

        gross_margin = []
        for gp, rev in zip(gross_profit, revenue):
            if gp is not None and rev is not None and rev != 0:
                gross_margin.append(round(gp / rev * 100, 2))
            else:
                gross_margin.append(None)

        r_and_d_pct = []
        for rd, rev in zip(r_and_d, revenue):
            if rd is not None and rev is not None and rev != 0:
                r_and_d_pct.append(round(rd / rev * 100, 2))
            else:
                r_and_d_pct.append(None)

        rev_cagr_3 = _cagr(revenue, 3)
        rev_cagr_5 = _cagr(revenue, 5)
        eps = _extract(fin, ["Diluted EPS", "Basic EPS"])
        eps_cagr_3 = _cagr(eps, 3)
        eps_cagr_5 = _cagr(eps, 5)

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
    """获取单只股票完整数据。"""
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
        if args.financials:
            # --financials in JSON mode: emit only financials + growth data
            output = []
            for r in results:
                entry = {"ticker": r.get("ticker", "?"), "name": r.get("name", "?")}
                if "error" in r:
                    entry["error"] = r["error"]
                else:
                    fin = r.get("financials", {})
                    entry["financials"] = fin
                    entry["growth"] = r.get("growth", {})
                    if isinstance(fin, dict) and "error" in fin:
                        entry["financials_error"] = fin["error"]
                output.append(entry)
            print(json.dumps(output if len(output) > 1 else output[0],
                             ensure_ascii=False, indent=2, default=str))
        else:
            output = results if len(results) > 1 else results[0]
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            if "error" in r:
                print(f"[ERROR] {r['ticker']}: {r['error']}")
                continue
            if args.financials:
                # --financials in text mode: show only financial data
                print("=" * 60)
                print(f"全球对标（仅财务）: {r['name']} ({r['ticker']})")
                print("=" * 60)
                fin = r.get("financials", {})
                if isinstance(fin, dict) and "error" in fin:
                    print(f"  [WARN] 财务数据获取失败: {fin['error']}")
                elif isinstance(fin, dict) and "years" in fin:
                    print(f"  财务年度:   {fin['years']}")
                    print(f"  营收:       {fin.get('revenue', '-')}")
                    print(f"  净利润:     {fin.get('net_income', '-')}")
                    print(f"  ROE:        {fin.get('roe', '-')}")
                    g = r.get("growth", {})
                    if g and "error" not in g:
                        for key, val in g.items():
                            if val is not None:
                                print(f"  {key}:  {val}%")
                else:
                    print("  [WARN] 未能获取财务数据")
            else:
                print("=" * 60)
                print(f"全球对标: {r['name']} ({r['ticker']})")
                print("=" * 60)
                q = r.get("quote", {})
                if isinstance(q, dict) and "error" in q:
                    print(f"  [WARN] 报价获取失败: {q['error']}")
                else:
                    print(f"  当前价:     {q.get('price', '-')}")
                    print(f"  总市值:     {q.get('market_cap', '-')}")
                    print(f"  PE(TTM):    {q.get('pe_ttm', '-')}")
                    print(f"  PB:         {q.get('pb', '-')}")
                fin = r.get("financials", {})
                if isinstance(fin, dict) and "error" in fin:
                    print(f"  [WARN] 财务数据获取失败: {fin['error']}")
                elif isinstance(fin, dict) and "years" in fin:
                    print(f"\n  财务年度:   {fin['years']}")
                    print(f"  营收:       {fin.get('revenue', '-')}")
                    print(f"  净利润:     {fin.get('net_income', '-')}")
                    print(f"  ROE:        {fin.get('roe', '-')}")


if __name__ == "__main__":
    main()
