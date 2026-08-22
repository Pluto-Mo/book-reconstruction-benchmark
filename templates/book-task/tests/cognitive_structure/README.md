# Cognitive structure verifier

这里放置由 `tests/gold/book_card.json` 生成的关系级 Judge criteria。裁判不得直接给文章总体印象分。

## 目录建议

```text
cognitive_structure/
├── evidence_locator/
│   ├── structure-cs01.toml
│   └── structure-cs02.toml
├── relation_adjudicator/
│   ├── relation-r01.toml
│   └── relation-r02-high-risk.toml
├── quote_validator/
└── graph_aggregator/
```

## 运行职责

### Evidence Locator

- 读取完整 `/app/submission.md`；
- 为目标关系寻找候选引文和位置；
- 不给分；
- 首次未找到时按冻结规则二次定位或全文复查。

### Relation Adjudicator

- 读取目标关系、候选引文和必要上下文；
- 检查方向、机制、条件、边界、立场归属和案例功能；
- 可以连接候选文章已明确表达的分散命题；
- 不得用原书知识补入缺失桥接命题。

高风险关系优先逐关系调用：

- 条件或否定范围；
- 关系反转；
- 作者与对手立场；
- 暂时假设与最终结论；
- 构成性案例；
- 校准中出现高假阳性的关系。

### Quote Validator

- 验证引文真实存在；
- 检查字符位置；
- 读取必要上下文，防止截断后含义反转。

### Graph Aggregator

- 按关系局部权重计算覆盖；
- 判断 `mandatory` 路径；
- 判断每个 `alternative_group`；
- 计算结构和全书的完整核心路径率；
- 确定性输出，不调用 LLM 发明总分。

## 输出

Pilot 至少输出：

```json
{
  "cognitive_relation_coverage": 0.68,
  "complete_core_path_rate": 0.31,
  "genericity_failure_rate": 0.14,
  "judge_disagreement_rate": 0.08
}
```

Judge 理由、置信度、Locator 重试次数和分歧率用于审计，不直接进入质量分。

生成 criteria 前，Book Card 必须处于 `human_reviewed` 或 `frozen`。正式榜单只接受 `frozen`。
