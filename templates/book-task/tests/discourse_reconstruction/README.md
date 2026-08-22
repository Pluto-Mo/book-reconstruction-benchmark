# Discourse reconstruction

该目录用于独立于认知结构的篇章关系重构评分。

推荐生产结构：

```text
discourse_reconstruction/
├── authorial_edge_recovery/
│   ├── source_excerpt_loader/
│   ├── submission_locator/
│   ├── edge_adjudicator/
│   └── position_reversal/
├── editorial_coherence/
│   ├── structure_extractor/
│   ├── local_progression/
│   ├── global_order/
│   ├── spine_connectivity/
│   ├── example_integration/
│   └── closure/
└── discourse_aggregator/
```

运行时读取：

```text
/tests/gold/book_card.json
/tests/gold/discourse_card.json
/app/submission.md
```

原则：

- 作者关系边必须来自人工审核的有意义边池，不能任意抽两个原书段落；
- 认知关系正确性是作者边得分门槛，不重复奖励内容正确；
- 正式面板对所有模型相同，冻结后不重采样；
- Pairwise 进行 A/B 位置反转；
- 编辑性连贯判断候选内部关系和受控扰动，不给整体“流畅度 1–10 分”；
- 所有聚合由程序完成；
- 引文、边、面板、扰动和理由进入审计日志。
