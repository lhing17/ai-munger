本文件用于配合/loop命令使用，实现批量操作。

## 每次循环
1. 每次从reports/pass-list-full.md中读取一只还未分析的股票。
2. 使用munger-orchestrator SKILL对这只股票进行深度分析，并生成完整的html报告。
3. 更新reports/pass-list-full.md，将已分析的股票在列表中标记为已分析。
4. 将分析结果汇总到reports/pass-results.md中。
5. 重复以上步骤，直到所有股票都被分析过。

## 注意事项
1. 严禁批量分析，每轮只能分析一只股票。
2. 不要参考pass-list-full.md中的评分，该评分只是之前快筛阶段基于ROE的临时评分。
