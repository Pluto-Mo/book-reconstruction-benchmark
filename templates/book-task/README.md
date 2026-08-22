# Book task template

这是单本书 Harbor task 的占位模板，不属于正式 dataset。

实例化时至少要完成：

1. 复制整个目录到项目根下的新任务目录；
2. 替换 `task.toml` 中的任务名和元数据；
3. 替换 `instruction.md` 的篇幅占位符；
4. 将私有书稿放入 `environment/source/`；
5. 计算书稿 SHA-256，并依据 Schema 生成 `tests/gold/book_card.json`；
6. 按 `docs/rubric-production.md` 完成 Builder、Auditor、Red-Team 和人工审核；
7. 从冻结的 Book Card 生成小批次二元 Judge criteria；
8. 加入 Oracle 参考输出并实现 Verifier；
9. 通过全局资格考试与该书冒烟测试；
10. 冻结任务后，再用 `harbor add` 加入 Dataset。

模板故意不可直接运行。不得用空 Book Card、未替换占位符或未经校准的整体 1–10 分 Judge 临时补齐。
