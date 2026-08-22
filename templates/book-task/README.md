# Book task template

这是单本书 Harbor Task 的占位模板，不属于正式 Dataset。

实例化时至少完成：

1. 复制整个目录到项目根下的新任务目录；
2. 替换 `task.toml` 中的任务名和元数据；
3. 替换 `instruction.md` 的篇幅占位符；
4. 将私有书稿放入 `environment/source/`；
5. 计算书稿 SHA-256，并建立稳定 Source Map；
6. 使用 `tests/gold/rubric_authoring.template.md` 完成核心问题、节点、关系、路径和案例分类；
7. 依据 `schemas/book-card.schema.json` 写入 `tests/gold/book_card.json`；
8. 运行 `scripts/validate_book_card.py`；
9. 按 `docs/rubric-production.md` 完成 Builder、Auditor、Red-Team 和人工审核；
10. 加入经审核 Oracle，并验证固定篇幅内满分可达；
11. 实现 Evidence Locator、Relation Adjudicator、Quote Validator 和 Graph Aggregator；
12. 通过全局资格考试与该书冒烟测试；
13. 冻结任务后，再用 `harbor add` 加入 Dataset。

验证示例：

```bash
uv run scripts/validate_book_card.py   --card <task>/tests/gold/book_card.json   --schema schemas/book-card.schema.json
```

模板故意不可直接运行。不得用空 Book Card、未替换占位符、扁平观点列表或未经校准的整体 1–10 分 Judge 临时补齐。
