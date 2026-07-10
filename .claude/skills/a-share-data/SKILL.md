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
