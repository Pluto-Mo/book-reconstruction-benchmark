# 认知评分运行契约

本文定义 V1 认知流水线中已经可以确定性执行的部分。它负责验证 Locator 与窄 Judge 的产物、核对候选引文、传播关系判决并聚合认知指标；它不负责调用某个模型，也不把开发期预期标签当成 Judge 输出。

## 1. 输入与职责边界

一次可评分运行需要：

1. 一张已经过结构校验的 Book Card；
2. 完整、未经归一化改写的 UTF-8 候选文章；
3. 每条认知关系恰好一条 Evidence Locator 结果；
4. 每条非 locator_error 关系恰好一条 Relation Adjudicator 结果。

运行顺序固定为：

~~~text
Evidence Locator 产物
→ Quote Validator
→ Relation Adjudicator 产物校验
→ Graph Aggregator
~~~

scripts/runtime_scoring.py 不调用 LLM。未来 Locator 或 Judge provider 可以替换，但它们必须产出相同 Schema，且不得改变聚合代码。

## 2. Evidence Locator 结果

Locator 使用 schemas/evidence-result.schema.json。

- found：至少有一条候选引文；
- none：候选引文为空，并且 attempts >= 2，表示首次失败后已经执行冻结的重试或全文复查；
- locator_error：基础设施失败，不是候选文章的语义失败。

字符位置是对完整 UTF-8 文件解码后的 Unicode code point 偏移，采用 Python 半开区间 [start_char, end_char)。Quote Validator 要求：

- quote 等于 submission[start_char:end_char]；
- 0 <= start_char < end_char <= len(submission)；
- candidate_id 在单条 Locator 结果内唯一；
- 如填写 context_before / context_after，它们必须是引文两侧紧邻的字面文本。

## 3. Relation Adjudicator 结果

窄 Judge 使用 schemas/judge-result.schema.json，并额外满足以下跨文件约束：

- book_id、submission_id、criterion_id 和 evidence_result_id 必须与 Locator 结果一致；
- selected_candidate_ids 必须来自已经通过 Quote Validator 的候选引文；
- missing_facets 只能来自该关系的 required_facets；
- support_found 或 contradiction_found 为真时，必须选择证据；
- locator_error 不得接收语义判决；
- 经两次定位仍为 none 时，Judge 记录为 fail，不得声称找到了支持或反证，并将该关系的全部必需 facet 标为缺失；
- abstain、复核 rejected 或 conflict 都保持未决，不得转写成 fail。

pass 仍须满足 Judge Schema 中的硬条件：有选中证据、找到支持、没有反证、没有缺失 facet。

## 4. 关系覆盖

结构内关系覆盖为：

\[
C_s = \frac{\sum_{r \in s} w_r y_r}{\sum_{r \in s} w_r}
\]

全书关系覆盖同时使用结构权重 \(W_s\) 与结构内关系权重 \(w_r\)：

\[
C_{\text{book}} =
\frac{\sum_s W_s \sum_{r \in s} w_r y_r}
{\sum_s W_s \sum_{r \in s} w_r}
\]

这里 pass = 1、fail = 0。叶子只在本书内部聚合；跨书时仍先得到每书结果，再做书级宏平均。

## 5. 路径完整率

路径计分单元有两种：

- 每条 mandatory 路径是一个单元；所有成员关系通过才完整；
- 同一 alternative_group 整体是一个单元；组内至少一条路径完整即通过。

同一替代组中的路径语义等价，因此必须使用相同权重；组只进入一次分母，不按候选路径条数重复加权。

若计分单元 \(u\) 的权重为 \(v_u\)，则：

\[
P_{\text{book}} =
\frac{\sum_s W_s \sum_{u \in s} v_u q_u}
{\sum_s W_s \sum_{u \in s} v_u}
\]

其中 \(q_u\) 表示该必需路径或替代组是否完整。每个结构另输出 path_complete：该结构所有必需路径和替代组都满足时才为真。它是审计字段，不在路径分母中重复计分。

## 6. 未决与基础设施失败

下列任一情况出现时，本次认知运行标记为 unscorable：

- 任一关系的 Locator 为 locator_error；
- 任一 Judge 为 abstain；
- 任一 Judge 复核为 rejected 或 conflict。

此时 cognitive_relation_coverage 与 complete_core_path_rate 都写为 null，不输出部分分数，也不把失败关系计作零。关系、结构和路径的局部状态仍保留在审计结果中，方便定位重试范围。

## 7. 输出与运行

聚合结果使用 schemas/cognitive-aggregate.schema.json。它只包含认知维度和审计字段，不包含跨维度 reward。

~~~bash
uv run scripts/runtime_scoring.py \
  --book-card path/to/book_card.json \
  --submission path/to/submission.md \
  --submission-id rollout-001 \
  --evidence-results path/to/evidence.jsonl \
  --judge-results path/to/judgments.jsonl \
  --output path/to/cognitive-aggregate.json
~~~

CLI 默认拒绝 status 为 draft 的 Book Card。开发调试可以显式添加 --allow-draft-card；正式 Harbor Task 仍只接受 frozen。

开发书的 19 个认知校准样例可执行离线聚合回放：

~~~bash
uv run scripts/replay_calibration.py
~~~

该回放把人工预期的关系变化当作夹具判决，只验证路径传播、权重、篇幅约束和输出协议；semantic_judge_exercised 固定为 false。它不能替代未来的 Locator 召回率、Judge 假阳性／假阴性和重复判决稳定性测试。
