# Cognitive structure

这里放置由 `tests/gold/book_card.json` 生成的证据优先二元 criteria。裁判不得直接给文章总体分。

## 组织方式

推荐每条核心关系生成一个 Judge TOML：

```text
cognitive_structure/
├── relation-r01.toml
├── relation-r02.toml
└── relation-r03-high-risk.toml
```

- 一个文件默认包含同一关系下的 3–8 个原子；
- 条件、否定范围、关系反转等高风险原子使用 `mode = "individual"`；
- 每个 criterion 使用 Book Card 中的稳定 `id`；
- Judge 只读 `/app/submission.md` 和相关卡片，不重新阅读整本书；
- Judge 必须先引用最短证据；没有证据则判 0；
- 引文需要独立做字符串存在性检查；
- Judge 理由和置信度只用于审计；
- 原子、关系和维度分数均由程序按冻结权重汇总。

生成 Judge 文件前，Book Card 必须处于 `human_reviewed` 或 `frozen` 状态。正式榜单只接受 `frozen`。
