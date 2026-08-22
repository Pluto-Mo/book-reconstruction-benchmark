# Calibration

校准集检验评分系统能否识别预先定义的认知损伤和篇章损伤。它不等于正式模型样本，也不证明 Judge 拥有普遍文学审美。

推荐目录：

```text
calibration/
├── global/
│   ├── cases.jsonl
│   └── expected.jsonl
└── books/
    └── <book-id>/
        ├── cognitive/
        │   ├── cases.jsonl
        │   └── expected.jsonl
        └── discourse/
            ├── cases.jsonl
            └── expected.jsonl
```

每个变体必须记录：

- 基准文本 ID；
- 只改变了什么；
- 哪些认知关系和路径应变化；
- 哪些作者边和编辑探针应变化；
- 哪些指标必须保持稳定；
- 人工确认人；
- Book Card、Discourse Card、Panel、Judge Prompt 和模型版本。

由 Agent 生成的扰动仍需 Benchmark 作者确认只改变目标变量。

开发期允许用确定性 mutation spec 生成变体，以减少手工复制产生的隐性改动。spec 至少绑定基准文本 SHA-256、精确操作、输出路径、预期输出 SHA-256 与计数；生成文本仍须落盘、接受独立语义审计并由 Human Owner 确认。mutation spec 证明字节级改动范围，不替代对“哪些关系、路径、作者边和探针应变化”的语义判断。

每个编辑探针必须完整落入 `changed / stable / unfrozen` 三态之一，三组不得重叠。存在未冻结作者边时，不得填写看似确定的精确恢复分数；先保留聚合结果未冻结，等取证范围、抽样和 Judge 全部固定后再二值化。

## 1. 认知校准

最低包括：

1. 语义保持改写；
2. 不改变认知功能的正确重组；
3. 只保留最终结论；
4. 删除核心关系；
5. 删除构成性案例；
6. 删除说明性案例；
7. 常识替换；
8. 术语堆砌；
9. 删除限定；
10. 关系反转；
11. 立场误认；
12. 改变认知功能的错误重排。

## 2. 篇章校准

最低包括：

1. `section_shuffle`：交换主要文章单元，保留句子；
2. `transition_flattening`：把有效转折压成“此外／其次”；
3. `definition_example_modularization`：改成一个概念一个模块；
4. `example_relocation`：把案例移动到不承担原功能的位置；
5. `generic_closure`：把结尾换成同领域通用总结；
6. `semantic_preserving_rewrite`：只改措辞，不改关系、顺序和功能。

## 3. 预期行为

| 变体 | 认知覆盖 | 作者边 | 编辑性连贯 |
|---|---|---|---|
| 语义保持改写 | 基本不变 | 基本不变 | 基本不变 |
| 正确重组 | 基本不变 | 若功能不变则稳定 | 可以稳定或提高 |
| 只保留结论 | 关系和路径下降 | 下游依赖下降 | 视文章而定 |
| 删除核心关系 | 对应关系失败 | 内容门槛失败 | 不要求机械下降 |
| 删除构成性案例 | 相关路径失败 | 案例边失败 | 案例嵌入下降 |
| 删除说明性案例 | 原则上稳定 | 非关键边可稳定 | 若删除冗余可稳定或提高 |
| 章节交换 | 原则上可稳定 | 涉及原书修辞边时下降 | `global_order` 下降 |
| 转场扁平化 | 认知可稳定 | 下游依赖可能下降 | `local_progression` 下降 |
| 模块化改写 | 术语和局部关系可稳定 | 控制性边下降 | 中心线和案例嵌入下降 |
| 案例错误移动 | 案例内容可保持 | 案例功能边下降 | `example_integration` 下降 |
| 通用结尾 | 前文认知稳定 | `opening_to_closure` 下降 | `closure` 下降 |

## 4. Judge 自身校准

至少报告：

- false positive / false negative；
- 关系反转、立场误认和构成性案例删除识别；
- 作者边修辞功能识别；
- A/B 位置反转分歧率；
- 章节交换和通用结尾识别；
- 语义保持改写稳定性；
- 重复 Judge 分歧；
- Locator 召回失败率。

## 5. 冻结纪律

开发书可以反复修改 Rubric、Panel、Probe 和 Judge。

保留书的以下内容必须在正式输出前冻结：

- 公开 instruction；
- Book Card；
- Discourse Card；
- Oracle；
- 作者边池和固定面板；
- 编辑探针和扰动算法；
- 校准文本和预期标签；
- 聚合与失败处理。

关键认知损伤或关键篇章扰动仍被判为完整通过时，不得冻结该书 Task。

## 6. 开发期聚合回放

scripts/replay_calibration.py 将认知 expected.jsonl 中的关系变化作为夹具判决，经过生产形态的确定性 Graph Aggregator，检查路径传播、加权指标和篇幅硬约束：

~~~bash
uv run scripts/replay_calibration.py
~~~

该命令不运行 Evidence Locator 或语义 Judge，输出中的 semantic_judge_exercised 因而固定为 false。19/19 通过只表示聚合实现与当前预期标签一致，不表示 Judge 已通过校准；正式冻结仍须分别测量 Locator 召回、Judge 假阳性／假阴性、重复判决和失败重试。
