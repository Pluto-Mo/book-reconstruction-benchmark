# 篇章语义运行层

本文记录 `scripts/discourse_semantic_runtime.py` 的开发期可执行协议。它实现 Discourse Card 已定义的两个子维度，但不代表 Card、Judge 模型或正式排行榜已经冻结。

## 输入与顺序

运行层只在认知流水线完成后启动：

```text
cognitive-aggregate.json (status=complete)
        ↓
严格 content gate
        ↓
Authorial Edge Locator → Quote Validator → Edge Judge
        ↓
Structure Extractor → 五类 Editorial Probe
        ↓
deterministic aggregate
```

输入为 Book Card、Discourse Card、认知聚合、`/app/submission.md`、冻结 provider 配置与 rollout index。Panel 只能由 Discourse Card 的 rollout 映射选择。

## Authorial Edge

每条边的门槛是关联认知关系的严格合取：全部 `pass` 才运行语义判断；任一 `fail` 直接得到 gated zero；任一未决或基础设施错误使本次作者边聚合不可评分。

门槛通过后，Locator 只看到窄 edge view 和候选全文，不看到 Source Anchor 摘要、hard negatives、权重或认知判决。它最多运行两次，第二次是全文复查。所有返回 quote 必须通过逐字连续子串和 code-point span 校验。

Edge Judge 看到目标边、候选证据和必要 source context，分别输出：

- `rhetorical_function_preserved`；
- `downstream_dependency_preserved`。

程序计算 `a_e = g_e × (0.5r_e + 0.5d_e)`，再按冻结面板权重和 stratum 聚合。Judge 不直接给面板总分。

当前开发 Task 为避免将未经审核的长原文发送到远程服务，仅发送 Book Card 的短证据摘要，并在结果中标记 `book_card_summaries_development_only`。这足以验证协议和校准流程，但不能作为正式冻结分数；正式运行还需要人工确认的私有短摘录。

## Editorial Coherence

Structure Extractor 输出中心问题、2–8 个主要单元的半开字符区间与功能，以及案例区间。程序检查区间、顺序、重叠、host unit 和允许角色。

五类探针按 Discourse Card 运行：

- `local_progression`：从相邻正文段落以稳定哈希选至多 8 对，三项布尔均值；
- `global_order`：从相邻主要单元选至多 4 对，每对比较原顺序与交换顺序，并执行 AB/BA 双位置反转；
- `spine_connectivity`：逐主要单元判断 orphan，程序计算 `1 - orphan/units`；
- `example_integration`：稳定抽至多 3 例，必须同时 integrated 且承担允许功能；
- `closure`：分别判断回到开头、依赖正文和非通用。

稳定抽样 key 为：

```text
SHA256("editorial-v1\0" + seed + "\0" + submission_sha256
       + "\0" + probe_name + "\0" + object_id)
```

同一文本、seed 和对象集合不会因进程随机数、模型输出顺序或供应商变化而重采样。任一必需结构或 Judge 调用不可判时，相关聚合为 `null`，不伪造模型零分。

## 输出

数值聚合写入 `discourse-aggregate.json`，并由 Harbor orchestrator 选择数值字段写入 `/logs/verifier/reward.json`。以下审计文件不进入 reward：

- `authorial-edge-results.jsonl`；
- `discourse-structure.json`；
- `editorial-probe-results.jsonl`；
- `discourse-events.jsonl`；
- `discourse-runtime-status.json`。

Provider 或协议在冻结的两次尝试后仍失败时，Harbor verifier 返回 `unscorable`，不写伪零 reward。
