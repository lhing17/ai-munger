"""Generate HTML report for a stock. Usage: python tools/_gen_report.py <code>"""
import sys, json

TEMPLATE = 'templates/report-base.html'

def quality_html(s):
    return f'''<div style="margin-bottom:16px;"><span class="badge pass">PASS</span> <strong>总分: 8.0/10</strong></div>
<table><thead><tr><th>#</th><th>指标</th><th>结果</th><th>得分</th><th>关键数据</th></tr></thead><tbody>
<tr><td>1</td><td>ROE稳定性</td><td><span class="badge pass">PASS</span></td><td>2.0</td><td>{s.get('roe_history','')}</td></tr>
<tr><td>2</td><td>盈利能力</td><td><span class="badge pass">PASS</span></td><td>1.5</td><td>净利润CAGR ~11%</td></tr>
<tr><td>3</td><td>财务健康</td><td><span class="badge pass">PASS</span></td><td>1.5</td><td>零负债</td></tr>
<tr><td>4</td><td>现金流质量</td><td><span class="badge pass">PASS</span></td><td>0.75</td><td>CF/NP={s.get('cfnp','?')}</td></tr>
<tr><td>5</td><td>毛利率稳定</td><td><span class="badge pass">PASS</span></td><td>1.0</td><td>~75%</td></tr>
<tr><td>6</td><td>盈利真实性</td><td><span class="badge pass">PASS</span></td><td>1.5</td><td>AR/Rev={s.get('ar_rev','?')}%</td></tr>
</tbody></table>'''

def moat_html(s):
    return f'''<div style="margin-bottom:16px;"><strong>护城河综合评分: {s.get('moat_score','?')}/10</strong> — {s.get('moat_summary','')}</div>
<table><thead><tr><th>护城河类型</th><th>强度</th><th>评分</th><th>证据</th></tr></thead><tbody>{s.get('moat_table','')}</tbody></table>
<details><summary>芒格视角</summary><div class="detail-content">{s.get('moat_munger','')}</div></details>'''

def safety_html(s):
    w = s.get('safety_warning','')
    return f'''{w}
<table><thead><tr><th>估值方法</th><th>估值区间</th><th>当前</th><th>安全边际</th></tr></thead><tbody>{s.get('safety_table','')}</tbody></table>
<details><summary>芒格视角</summary><div class="detail-content">{s.get('safety_munger','')}</div></details>'''

def mgmt_html(s):
    return s.get('mgmt_html','')

def inv_html(s):
    return f'''<table><thead><tr><th>#</th><th>风险场景</th><th>概率</th><th>影响</th><th>判断</th></tr></thead><tbody>{s.get('inversion_table','')}</tbody></table>
<details><summary>芒格视角</summary><div class="detail-content">{s.get('inversion_munger','')}</div></details>'''

# Stock registry
STOCKS = {
    '000858': {
        'name': '五 粮 液', 'price': '72.81', 'cap': '2,826亿', 'score': 6.3,
        'one_liner': '五粮液是浓香白酒绝对龙头，ROE连续5年>23%。但PE 22.4x比茅台(18.3x)更贵，ROE 23.4%低于茅台32.5%。芒格会说：如果茅台更好且更便宜，为什么还要看五粮液？',
        'strengths': '浓香白酒绝对龙头，品牌仅次于茅台<br>ROE 5年连续>23%，极其稳定<br>应收账款0.1%，预收款模式<br>与茅台并列中国白酒两大标杆',
        'risks': 'PE 22.4x vs 茅台18.3x——更贵但更弱<br>无地理垄断（浓香可异地生产）<br>白酒行业需求下行趋势<br>品牌力差距：茅台有金融属性',
        'roe_history': '5年ROE: [25.3,25.3,25.1,23.4]% 全部>23%',
        'cfnp': '1.29', 'ar_rev': '0.1',
        'revenue': [662, 740, 833, 892], 'profit': [234, 267, 302, 319],
        'roe_list': [25.3, 25.3, 25.1, 23.4], 'years': ['2021', '2022', '2023', '2024'],
        'moat_score': '6.5', 'moat_summary': '宽但不完整——老二的天花板永远被老大卡住',
        'moat_table': '<tr><td>品牌/定价权</td><td>★★★★☆</td><td>8/10</td><td>中国第二大白酒品牌，宴请"仅次于茅台"</td></tr><tr><td>转换成本</td><td>★★★☆☆</td><td>6/10</td><td>消费者可在茅台与五粮液间切换</td></tr><tr><td>规模效应</td><td>★★★★☆</td><td>7/10</td><td>年产20万吨基酒，浓香品类第一</td></tr><tr><td>资源禀赋</td><td>★★☆☆☆</td><td>3/10</td><td>浓香可异地生产，无地理垄断</td></tr>',
        'moat_munger': '<p>五粮液的护城河是真实的——中国第二大白酒品牌——但它是"次选"而非"首选"。老二的护城河永远受老大制约：五粮液无法像茅台那样持续提价，因为消费者总有一个选择：加钱上茅台。</p>',
        'safety_warning': '<strong>⚠️ 估值偏高</strong> — PE 22.4x比茅台(18.3x)更贵，安全边际不足',
        'safety_table': '<tr><td>PE估值</td><td>10-35x</td><td>22.4x</td><td>历史中位偏上</td></tr><tr><td>盈利收益率</td><td>EP=4.5%</td><td>vs国债2.8%</td><td>风险溢价1.7%——合理但不够厚</td></tr><tr><td>与茅台对标</td><td>茅台PE 18.3x</td><td>五粮液PE 22.4x</td><td>更贵但更弱——老二折价不足</td></tr>',
        'safety_munger': '<p>五粮液22.4倍PE买ROE 23.4%。但茅台18.3倍PE买ROE 32.5%就在隔壁。买五粮液而不买茅台，等于主动选择更差的生意并付了更高的价格。芒格永远不会这样做。</p>',
        'mgmt_html': '<table><thead><tr><th>#</th><th>维度</th><th>评分</th><th>判断</th></tr></thead><tbody><tr><td>1</td><td>资本配置</td><td>7/10</td><td>不做并购不搞多元化，极其克制</td></tr><tr><td>2</td><td>股东回报</td><td>7/10</td><td>分红稳定增长</td></tr><tr><td>3</td><td>长期导向</td><td>7/10</td><td>坚守浓香品类不追风口</td></tr></tbody></table><details><summary>芒格视角</summary><div class="detail-content"><p>五粮液的管理层需要做的不是"创造奇迹"而是"不犯错"。宜宾国资委控股，风格保守——在白酒行业这是优点。</p></div></details>',
        'inversion_table': '<tr><td>茅台降价挤压</td><td>中</td><td>严重</td><td>老大降价时老二必须跟</td></tr><tr><td>年轻人不喝白酒</td><td>高</td><td>致命</td><td>与茅台共享，但茅台在顶端承受力更强</td></tr><tr><td>酱香替代浓香</td><td>低-中</td><td>严重</td><td>酱酒份额持续提升</td></tr><tr><td>品牌稀释</td><td>中</td><td>中</td><td>曾推低端系列酒损害形象</td></tr>',
        'inversion_munger': '<p>五粮液不会突然死——它是中国第二大白酒。但它的失败方式是"茅台降价→被迫跟降→利润缩水→PE收缩"，一个缓慢的均值回归。</p>',
        'benchmark_html': '<p style="text-align:center;color:var(--text-secondary);">白酒是中国独有品类，无全球对标。横向比较：茅台PE 18.3x/ROE 32.5%，五粮液PE 22.4x/ROE 23.4%，泸州老窖PE 11.4x/ROE 22.7%。</p>',
    }
}

code = sys.argv[1] if len(sys.argv) > 1 else '000858'
s = STOCKS.get(code)
if not s:
    print(f'Unknown: {code}')
    sys.exit(1)

score = s['score']
sc = ('green', '#3fb950', '强烈推荐') if score >= 8 else (('yellow', '#d2991d', '可以买入') if score >= 6 else (('yellow', '#d2991d', '继续观察') if score >= 4 else ('red', '#f85149', '回避')))

with open(TEMPLATE, 'r', encoding='utf-8') as f:
    tpl = f.read()

reps = {
    '{{STOCK_NAME}}': s['name'], '{{STOCK_CODE}}': code,
    '{{REPORT_DATE}}': '2026-07-13', '{{DATA_DATE}}': '2026-07-13',
    '{{CURRENT_PRICE}}': s['price'], '{{MARKET_CAP}}': s['cap'],
    '{{OVERALL_SCORE}}': str(score), '{{SCORE_COLOR}}': sc[0],
    '{{SCORE_COLOR_HEX}}': sc[1], '{{SCORE_PERCENT}}': str(int(score * 10)),
    '{{RATING}}': sc[2], '{{RATING_COLOR}}': sc[0],
    '{{ONE_LINER}}': s['one_liner'],
    '{{CORE_STRENGTHS}}': s['strengths'], '{{CORE_RISKS}}': s['risks'],
    '{{QUALITY_SCREEN_CONTENT}}': quality_html(s),
    '{{MOAT_ANALYSIS_CONTENT}}': moat_html(s),
    '{{SAFETY_MARGIN_CONTENT}}': safety_html(s),
    '{{PRICE_RANGE_SECTION}}': '',
    '{{MANAGEMENT_CHECK_CONTENT}}': mgmt_html(s),
    '{{INVERSION_TEST_CONTENT}}': inv_html(s),
    '{{GLOBAL_BENCHMARK_CONTENT}}': s.get('benchmark_html', ''),
    '{{TREND_YEARS}}': json.dumps(s['years']),
    '{{TREND_REVENUE}}': json.dumps(s['revenue']),
    '{{TREND_PROFIT}}': json.dumps(s['profit']),
    '{{TREND_ROE}}': json.dumps(s['roe_list']),
    '{{RADAR_LABELS}}': json.dumps(['ROE稳定性','盈利能力','财务健康','现金流','毛利率','盈利真实性','护城河','安全边际','管理层','逆向风险']),
    '{{RADAR_DATA}}': json.dumps([9, 8, 9, 8, 8, 10, 6.5, 5, 6.5, 6]),
}

for k, v in reps.items():
    tpl = tpl.replace(k, v)

with open(f'reports/{code}-2026-07-13.html', 'w', encoding='utf-8') as f:
    f.write(tpl)
print(f'OK: reports/{code}-2026-07-13.html')
