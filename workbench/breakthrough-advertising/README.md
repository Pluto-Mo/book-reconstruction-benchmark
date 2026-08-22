# 《突破性广告》Rubric 开发工作台

本目录是开发书的 Rubric 工作区，不是正式 Harbor Task，也不进入 `dataset.toml`。

当前状态：`draft`。

## 输入边界

- 书名：Eugene M. Schwartz, *Breakthrough Advertising*（本地中英文合订 OCR Markdown）
- 文档 SHA-256：`e077e6b8467b30b9499a48021a0b360f87c43a2442a0d3a42d420efd74274a3c`
- 书稿正文没有复制进仓库。
- 定位使用哈希绑定源文件的语言中立 `src` 行空间；双语内容只是本书可用的 OCR 互校条件，不是跨书评分规则。
- 这份 OCR 不是无误正典。关键关系冻结前仍需人工对照可靠原版。

## 当前产物

- `source_map.md`：双语章节范围、定位方案与 OCR 风险。
- `rubric_authoring.md`：一级认知结构、纳入/排除理由和 Human Owner 决策项。
- `book_card.draft.json`：按 `schemas/book-card.schema.json` 编写的关系级 Book Card 草案。
- `discourse_authoring.md`：作者关系边池、固定面板、编辑性探针与扰动设计工作表。
- `discourse_card.draft.json`：按 `schemas/discourse-card.schema.json` 编写的篇章关系重构卡草案。
- `length_ablation.md`：无篇幅、8000、6000、4000、3000 字条件的开发消融协议，以及正式主榜的单一篇幅冻结规则。
- `oracle_unconstrained.draft.md`：第一版无评分篇幅约束 Oracle；按原作者自然展开论证的声音重新编辑，但口吻不计分、不作 Judge 参照；正文无拉丁字母。canonical 整文件计数为 7,177，排除 Markdown 标题行的正文诊断值为 6,998。
- `oracle_unconstrained.trace.md`：不公开给被评 Agent 的反向覆盖轨迹，逐项定位 60 条关系、16 条 mandatory paths 和 19 条开发篇章边。
- `oracle_l8000.draft.md`、`oracle_l6000.draft.md`、`oracle_l4000.draft.md`、`oracle_l3000.draft.md`：四个 max-only 条件的独立中文 reference 改写；canonical 整文件计数依次为 6,362、4,186、3,051、2,646。
- `oracle_l8000.trace.md`、`oracle_l6000.trace.md`、`oracle_l4000.trace.md`、`oracle_l3000.trace.md`：各受限稿的覆盖定位、审计历史和 Human Owner 边界。
- `length_curve.draft.md` 与 `length_runs.draft.jsonl`：reference 可达性曲线及其机器可读哈希、计数、卡片版本和预期覆盖记录。
- `perturbations/`：由哈希绑定 mutation spec 生成的十六份单变量负向文本与一份正确重组正向对照；负向条件除关系反转、限定前提删除、章节交换和四个构成性案例整案删除外，已覆盖转场扁平化、定义—案例模块化、案例错误搬移、通用结尾、结论孤立、常识替换、术语堆砌、立场误认和独立核心关系删除。
- `relationship_application.md`：面向 Human Owner 解释认知关系、必经路径和 19 条篇章边如何实际控制文章。
- `audit_report.md`：自动校验结果、人工抽查范围与冻结前风险。

## 不能从当前状态推断的事项

- `draft` 不表示内容已获人工认可。
- 第一阶段先制作无评分篇幅约束的 Oracle；`6000–8000` 只保留为正式主榜候选区间，尚未冻结。
- 默认等权不表示关系重要性已经校准。
- 四个构成性案例已经 Human Owner 暂定批准，且各自已有独立整案删除样本；十六份负向变体与正确重组对照目前只验证了预期标签的语义边界，尚未由生产 Judge 实测其可分辨性。
- 全部 Oracle 和校准标签仍是 `draft`，覆盖轨迹通过不等于 Human Owner 已认可成文质量或金卡内容；Judge criteria 和可运行 Verifier 仍未完成。

## 下一道闸门

八个一级认知结构、四个构成性案例和 19-edge 开发面板已经 Human Owner 暂定通过；五版长度 reference 与隐藏 trace 已完成，十六份负向样本和一份正确重组对照也已生成并独立审计。下一道闸门是 Human Owner 逐版审读，并实现 Locator / Judge / Verifier，在本书上实测这些标签与五档同构 instruction；在生产评分链可运行以前不冻结主榜篇幅。
