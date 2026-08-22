# 认知语义运行层

本文说明 Evidence Locator 与 Relation Adjudicator 如何接入具体模型，同时保持评分协议、Prompt 和聚合器不随厂商变化。

## 1. 三层边界

认知运行分成三层：

~~~text
Book Card
→ verifier-only 逐关系 criteria
→ provider-neutral 结构化模型请求
→ Evidence / Judge 标准结果
→ deterministic runtime_scoring
~~~

具体厂商只存在于中间的 adapter。更换被测模型或 Judge 服务时，不得修改 criteria、Prompt、输出 Schema、重试次数和聚合器。

## 2. Criteria 编译

scripts/compile_cognitive_criteria.py 从 Book Card 为每条关系生成一条 verifier-only criterion。生成内容只包含：

- 目标关系类型和窄 requirement；
- 关系两端必要节点的 statement、argument role、stance owner 与 epistemic status；
- required facets；
- 可接受释义、pass/fail 边界、常见假阳性和矛盾模式；
- 由关系自身派生的风险标记；
- Prompt 内容哈希版本。

以下内容禁止进入 criteria：

- Source Anchor ID 或原书 locator；
- 关系、路径或结构权重；
- critical 标记；
- 其他路径、其他关系和 genericity traps。

criteria 是隐藏 verifier 材料，不能写入公开 instruction，也不能暴露给被测 Agent。Locator 看到的范围还会进一步缩小：它不接收 pass_if、fail_if、常见假阳性或矛盾模式，只接收定位所需的目标关系描述。

开发书编译命令：

~~~bash
uv run scripts/compile_cognitive_criteria.py \
  --book-card workbench/breakthrough-advertising/book_card.draft.json \
  --allow-draft-card \
  --output workbench/breakthrough-advertising/runtime/cognitive_criteria.draft.jsonl \
  --manifest workbench/breakthrough-advertising/runtime/cognitive_criteria.manifest.draft.json
~~~

正式运行不得使用 --allow-draft-card。

## 3. Command Provider 协议

当前冻结的是厂商无关的单次 JSON 子进程协议：

1. runtime 不经 shell 启动 config.command；
2. 向 stdin 写入一个符合 schemas/model-request.schema.json 的 JSON 对象；
3. adapter 把 messages、model_id、generation_parameters 和 response_schema 映射到具体服务；
4. adapter 在 stdout 只写一个解析后的 JSON 对象；
5. adapter 日志写 stderr；runtime 对失败 stderr 只记录长度和 SHA-256，不把原文写入审计文件；
6. API 凭据只从 verifier 环境继承，不写配置、不写请求、不写仓库。

Locator adapter 输出 schemas/locator-model-response.schema.json。模型只复制逐字 quote；字符偏移由 runtime 在完整 submission 中确定性求出。quote 不存在、重复而无上下文可区分或上下文不符，均属于协议失败，不能变成语义 fail。

Judge adapter 输出 schemas/judge-model-response.schema.json。runtime 再注入对象 ID、模型与 Prompt 版本，并使用正式 judge-result Schema 和 Quote Validator 二次验证。

## 4. 固定重试

max_protocol_attempts 固定为 2：

- Locator 第一次为 none、伪引文或无效 JSON 时，第二次切换到 full_text_review；
- 第二次仍为 none，才生成语义 fail 所需的 none evidence；
- 两次都是 provider 或协议错误，生成 locator_error；
- Judge 返回无效 JSON、未知 candidate ID 或自相矛盾结果时重试一次；
- Judge 两次协议失败后生成 abstain。

locator_error 和 abstain 都使本次认知运行 unscorable，不会计作模型零分。

## 5. 配置与可复现性

配置格式见 schemas/cognitive-provider-config.schema.json，示例见 configs/cognitive-provider.example.json。正式配置至少冻结：

- adapter command；
- 完整 model_id；
- temperature、top_p、max_output_tokens 和 seed；
- timeout；
- 最大并发数；
- 两次协议尝试；
- Locator 上下文窗口。

runtime 状态文件记录 provider config SHA-256、criteria SHA-256、model_id、book_id 与 submission_id。比较运行期间不得替换配置或模型版本。

关系仍逐条隔离判定，但不同关系可以按冻结的 max_concurrency 并发执行。输出始终恢复为 criteria 顺序，调用完成先后不会改变 JSONL 顺序或聚合结果。

## 6. 单篇运行

~~~bash
uv run scripts/cognitive_semantic_runtime.py \
  --book-card path/to/book_card.json \
  --criteria path/to/cognitive_criteria.jsonl \
  --criteria-manifest path/to/cognitive_criteria.manifest.json \
  --submission path/to/submission.md \
  --submission-id rollout-001 \
  --provider-config path/to/frozen-provider.json \
  --output-dir path/to/runtime-output
~~~

输出：

- evidence-results.jsonl；
- judge-results.jsonl；
- semantic-events.jsonl；
- cognitive-aggregate.json；
- semantic-runtime-status.json。

语义运行完整时退出 0；产生 unscorable 审计结果时退出 2；输入、Schema 或配置错误时退出 1。

## 7. 校准结果核验

对 19 个开发校准文本分别运行后，将输出按 case_id 放置：

~~~text
runs/
└── BA-CAL-.../
    ├── evidence-results.jsonl
    ├── judge-results.jsonl
    └── cognitive-aggregate.json
~~~

然后运行：

~~~bash
uv run scripts/evaluate_cognitive_semantic_runs.py \
  --runs-dir runs \
  --output semantic-calibration-report.json
~~~

评估器会重新执行 Quote Validator 和 Graph Aggregator，而不是信任已保存的总分；并分别报告 damaged relation 错误通过、stable relation 错误失败、Locator error、Judge abstain 和路径传播差异。

## 8. 当前冻结边界

已经实现并测试的是 criteria 编译、静态泄漏审计、Command Provider 协议、两次定位、逐字 quote 解析、窄 Judge 规范化和确定性聚合。

尚未选择或冻结具体 Judge 厂商／模型，也没有把示例 adapter 当成生产 adapter。review_policy 目前只记录高风险关系，是否追加独立复核调用要在真实模型校准后冻结，不能在比较途中改变。
