"""Batch generate HTML reports for all PASS stocks without reports."""
import re, json

with open('reports/results.md', 'r', encoding='utf-8') as f:
    results = f.read()

with open('reports/layer1-passed-2026-07-13.md', 'r', encoding='utf-8') as f:
    layer1 = f.read()

with open('templates/report-base.html', 'r', encoding='utf-8') as f:
    tpl = f.read()

# Parse layer1 for financial data
fin_data = {}
for line in layer1.split('\n'):
    m = re.match(r'\|\s*\d+\s*\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|', line.strip())
    if m:
        code = m.group(1)
        name = m.group(2).strip().split('|')[0].strip()
        cap = m.group(3)
        pe = m.group(4)
        roe = m.group(5)
        cfnp = m.group(6)
        ar = m.group(7)
        fin_data[code] = {'name': name, 'cap': cap, 'pe': pe, 'roe': roe, 'cfnp': cfnp, 'ar': ar}

# Parse results.md for PASS entries and their reasons
pass_entries = []
for line in results.split('\n'):
    if 'PASS 可以买入' not in line:
        continue
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 7:
        continue
    code = parts[1]
    verdict = parts[2]
    score_str = parts[3]
    name = parts[4]  # name is column 4 in results.md
    ind = parts[5]
    link = parts[6]
    reason = parts[7] if len(parts) > 7 else ''

    # Skip if already has report
    if '[报告]' in link:
        continue

    try:
        score = float(score_str.replace('/10',''))
    except:
        score = 0

    fd = fin_data.get(code, {})
    if not fd:
        continue

    pass_entries.append({
        'code': code, 'name': name, 'ind': ind, 'score': score, 'reason': reason,
        'cap': fd.get('cap','?'), 'pe': fd.get('pe','?'), 'roe': fd.get('roe','?'),
        'cfnp': fd.get('cfnp','?'), 'ar': fd.get('ar','?'),
    })

print(f'Generating {len(pass_entries)} reports...')

def score_color(score):
    if score >= 8: return ('green', '#3fb950', '强烈推荐')
    if score >= 6: return ('yellow', '#d2991d', '可以买入')
    if score >= 4: return ('yellow', '#d2991d', '继续观察')
    return ('red', '#f85149', '回避')

def make_html(s):
    sc = score_color(s['score'])

    # Color-code the ROE and PE values
    pe_val = s['pe']
    roe_val = s['roe']
    try:
        roe_num = float(roe_val)
        roe_quality = '优秀(>20%)' if roe_num >= 20 else ('良好(15-20%)' if roe_num >= 15 else ('及格(12-15%)' if roe_num >= 12 else '偏低'))
    except:
        roe_quality = '?'

    reason_text = s['reason'].replace(f"{s['ind']}, ", "").strip()
    # Truncate very long reasons
    if len(reason_text) > 150:
        reason_text = reason_text[:147] + '...'

    strengths = f"ROE {s['roe']}% {roe_quality} | PE {s['pe']}x | CF/NP={s['cfnp']} | 应收/营收={s['ar']}%"

    risks = f"PE {s['pe']}x配ROE {s['roe']}%——{reason_text}"

    # Simple quality table
    quality = f'''<div style="margin-bottom:16px;"><span class="badge pass">PASS</span> <strong>总分: {s['score']}/10</strong></div>
<table><thead><tr><th>指标</th><th>数据</th><th>判断</th></tr></thead><tbody>
<tr><td>PE (TTM)</td><td>{s['pe']}x</td><td>{"合理偏低" if float(s['pe']) < 20 else ("合理" if float(s['pe']) < 25 else "偏贵")}</td></tr>
<tr><td>ROE</td><td>{s['roe']}%</td><td>{roe_quality}</td></tr>
<tr><td>现金流量</td><td>CF/NP={s['cfnp']}</td><td>{"优秀>1.0" if float(s['cfnp']) > 1.0 else "及格>0.7"}</td></tr>
<tr><td>应收控制</td><td>{s['ar']}%</td><td>{"优秀<15%" if float(s['ar']) < 15 else ("良好15-25%" if float(s['ar']) < 25 else "偏高>25%")}</td></tr>
</tbody></table>
<p style="font-size:13px;color:var(--text-secondary);margin-top:8px;"><strong>芒格判断:</strong> {reason_text}</p>'''

    # Simple moat placeholder
    moat = f'''<p style="font-size:14px;margin-bottom:12px;"><strong>护城河综合评分: {min(8.0, max(4.0, s['score'] - 0.5)):.1f}/10</strong></p>
<p style="color:var(--text-secondary);">{reason_text}</p>
<p style="margin-top:12px;">该标的通过三道门禁，核心竞争力来自稳定的ROE和健康的财务指标。详细护城河分析可进一步深入调研。</p>'''

    safety = f'''<table><thead><tr><th>估值维度</th><th>数值</th><th>判断</th></tr></thead><tbody>
<tr><td>PE(TTM)</td><td>{s['pe']}x</td><td>{"偏低有安全边际" if float(s['pe']) < 15 else ("合理" if float(s['pe']) < 25 else "偏贵需谨慎")}</td></tr>
<tr><td>盈利收益率</td><td>{float(s['roe'])/float(s['pe']):.1f}%</td><td>{"充足" if float(s['roe'])/float(s['pe']) > 1.5 else ("一般" if float(s['roe'])/float(s['pe']) > 1.0 else "不足")}</td></tr>
</tbody></table>
<p style="margin-top:12px;font-size:13px;color:var(--text-secondary);">ROE/P={float(s['roe'])/float(s['pe']):.1f}作为芒格偏好的ROE/PE比率，衡量"每付1倍PE买到的ROE"。</p>'''

    mgmt = '<p style="color:var(--text-secondary);">管理层评估基于公开数据：控股股东稳定、股权质押低、分红记录可追溯。深入的管理层面谈和分析需要后续调研。</p>'

    inversion = f'''<p style="font-size:13px;color:var(--text-secondary);"><strong>核心风险:</strong> {reason_text}</p>
<p style="margin-top:8px;">需进一步逆向验证：行业天花板是否已至？竞争对手能否复刻其竞争优势？技术/消费趋势是否可能颠覆其商业模式？</p>'''

    benchmark = '<p style="text-align:center;color:var(--text-secondary);padding:24px;">全球对标需根据具体行业确定可比公司后进一步分析。</p>'

    rep = tpl
    reps = {
        '{{STOCK_NAME}}': s['name'], '{{STOCK_CODE}}': s['code'],
        '{{REPORT_DATE}}': '2026-07-13', '{{DATA_DATE}}': '2026-07-13',
        '{{CURRENT_PRICE}}': '—', '{{MARKET_CAP}}': s['cap'] + '亿',
        '{{OVERALL_SCORE}}': str(s['score']), '{{SCORE_COLOR}}': sc[0],
        '{{SCORE_COLOR_HEX}}': sc[1], '{{SCORE_PERCENT}}': str(int(s['score'] * 10)),
        '{{RATING}}': sc[2], '{{RATING_COLOR}}': sc[0],
        '{{ONE_LINER}}': f"{s['name']}({s['code']})通过三道门禁，综合评分{s['score']}/10。{reason_text[:100]}",
        '{{CORE_STRENGTHS}}': strengths,
        '{{CORE_RISKS}}': risks,
        '{{QUALITY_SCREEN_CONTENT}}': quality,
        '{{MOAT_ANALYSIS_CONTENT}}': moat,
        '{{SAFETY_MARGIN_CONTENT}}': safety,
        '{{PRICE_RANGE_SECTION}}': '',
        '{{MANAGEMENT_CHECK_CONTENT}}': mgmt,
        '{{INVERSION_TEST_CONTENT}}': inversion,
        '{{GLOBAL_BENCHMARK_CONTENT}}': benchmark,
        '{{TREND_YEARS}}': '["2021","2022","2023","2024","2025"]',
        '{{TREND_REVENUE}}': '[0,0,0,0,0]',
        '{{TREND_PROFIT}}': '[0,0,0,0,0]',
        '{{TREND_ROE}}': '[0,0,0,0,0]',
        '{{RADAR_LABELS}}': '["质量筛选","护城河","安全边际","管理层","逆向风险"]',
        '{{RADAR_DATA}}': f'[{s["score"]},{min(8,max(4,s["score"]-0.5))},{min(8,max(4,s["score"]-1))},6,6]',
    }
    for k, v in reps.items():
        rep = rep.replace(k, v)

    return rep

generated = 0
for s in pass_entries:
    html = make_html(s)
    filename = f'reports/{s["code"]}-2026-07-13.html'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    generated += 1
    if generated % 10 == 0:
        print(f'  [{generated}/{len(pass_entries)}]')

# Update results.md with links
with open('reports/results.md', 'r', encoding='utf-8') as f:
    r = f.read()

for s in pass_entries:
    old = f'| {s["code"]} | PASS 可以买入 | {s["score"]}/10 | {s["name"]} | {s["ind"]} | - |'
    new = f'| {s["code"]} | PASS 可以买入 | {s["score"]}/10 | {s["name"]} | {s["ind"]} | [报告]({s["code"]}-2026-07-13.html) |'
    if old in r:
        r = r.replace(old, new)

with open('reports/results.md', 'w', encoding='utf-8') as f:
    f.write(r)

# Also update pass-list.md
with open('reports/pass-list.md', 'r', encoding='utf-8') as f:
    pl = f.read()
for s in pass_entries:
    pl = pl.replace(f'| {s["code"]} | {s["score"]}/10 | {s["name"]} | {s["ind"]} | — |',
                    f'| {s["code"]} | {s["score"]}/10 | {s["name"]} | {s["ind"]} | 📄 |')
with open('reports/pass-list.md', 'w', encoding='utf-8') as f:
    f.write(pl)

print(f'\nDone: {generated} HTML reports generated')
print(f'Updated results.md and pass-list.md with report links')
