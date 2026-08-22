# Discourse Reconstruction Authoring Worksheet

> 这是构建者工作表，不是公开题面。完成后把确认内容写入 `discourse_card.json`。

## A. 链接与冻结

- `book_id`：
- 书稿 SHA-256：
- Book Card SHA-256：
- 开发书 / 保留书：
- 作者关系边池负责人：
- 人工审核人：

## B. 作者关系边池

不要从全书任意随机抽段落对。先确认两块原书材料之间确有重要篇章关系，再写入边池。

为每条边填写：

| Edge ID | Source A | Source B | Linked cognitive relations | Edge type | Rhetorical role | Stratum | Critical | Weight |
|---|---|---|---|---|---|---|---:|---:|
| AE-__ |  |  |  |  |  |  |  |  |

逐边回答：

- 正确关系说明：
- A/B 的方向是否不可反转：
- 这条边在全书中承担什么层级或修辞功能：
- 候选文章后续哪些内容应当使用它：
- 如果只分别提到 A、B，为什么仍不足：
- Hard Negative 1（方向反转）：
- Hard Negative 2（关系并列化）：
- Hard Negative 3（限定／功能删除）：
- 候选文章如何直接取证：
- 它是否与认知关系重复奖励；若是，如何设置 content gate：

检查：

- [ ] 两端都能解析到 Book Card 的 Source Anchor。
- [ ] 至少有一个明确修辞功能或下游依赖。
- [ ] 不是任意相关段落，也不是单纯主题相似。
- [ ] 语义正确性只作门槛，不在篇章分重复奖励。
- [ ] 关键边可被 Oracle 在固定篇幅内恢复。

## C. 分层固定面板

- Random seed：
- 面板数量：
- 每个面板适用 Rollout：
- 所有模型是否使用同一面板：必须是 `true`
- 正式输出后是否重采样：必须是 `false`
- Pairwise 是否位置反转：必须是 `true`

| Panel ID | Edge IDs | Rollout indices | 覆盖 strata |
|---|---|---|---|
| PANEL-__ |  |  |  |

检查：

- [ ] 所有关键边至少进入一个面板。
- [ ] 面板覆盖冻结的全部必需 strata。
- [ ] 同一个 Rollout 不会被两个面板同时分配。
- [ ] Panel IDs 在查看正式模型输出前冻结。

## D. 编辑性连贯探针

### D1. Structure extraction

- 最大主要单元数：
- 是否参考标题但不机械依赖标题：
- 是否要求字符范围：必须是 `true`
- 允许的单元功能：

### D2. Local progression

- 相邻段落抽样数：
- 冻结选择算法：`deterministic_hash`
- 三个判据：
  - `relation_identifiable`
  - `forward_dependency`
  - `advances_argument`

### D3. Global order

- 主要单元交换对数量：
- 位置反转：必须是 `true`
- 一胜一负如何处理：`tie = 0.5`
- 如何防止 Judge 只根据“前文所述”等表面词判断：

### D4. Spine connectivity

- 控制性问题／中心命题：
- 主要单元可接受功能：
- `orphan` 定义：

### D5. Example integration

- 案例抽查数：
- 可接受功能：evidence / counterexample / boundary / turn / application / synthesis
- 如何区分论证功能与装饰性举例：

### D6. Closure

- 开头定位范围：
- 结尾定位范围：
- 三个判据：returns_to_opening / depends_on_body / non_generic

## E. 权重

### 编辑性连贯内部

| Metric | Weight | 理由 |
|---|---:|---|
| local_progression |  |  |
| global_order |  |  |
| spine_connectivity |  |  |
| example_integration |  |  |
| closure |  |  |

权重总和必须等于 1。

### 篇章维度内部

| Metric | Weight |
|---|---:|
| authorial_edge_recovery |  |
| editorial_coherence |  |

权重总和必须等于 1。认知结构与篇章关系如何合成最终主分不在此卡冻结。

## F. 受控扰动

| Perturbation | 只改变什么 | 应下降 | 应稳定 |
|---|---|---|---|
| section_shuffle |  | global_order | cognitive coverage |
| transition_flattening |  | local progression | factual content |
| definition_example_modularization |  | spine / example integration | term coverage |
| example_relocation |  | authorial edge / example integration | example count |
| generic_closure |  | closure | body cognition |
| semantic_preserving_rewrite | wording only | none | all substantive metrics |

检查：

- [ ] 每个扰动经过人工确认，只改变目标变量。
- [ ] 语义保持改写不会系统性降分。
- [ ] 章节交换可以与认知覆盖变化解耦。
- [ ] A/B 位置反转冲突不会被强行判胜。

## G. Oracle 与冻结

- Oracle 的 `authorial_edge_recovery`：
- Oracle 的五个编辑子分：
- Oracle 的 `editorial_coherence`：
- 是否存在另一种正确组织也可高分：
- 高认知知识笔记锚点是否明显低于 Oracle 的篇章分：
- 流畅通用文章锚点是否无法通过作者边 content gate：

冻结前：

- [ ] Discourse Card 已通过 Schema 和交叉引用验证。
- [ ] Book Card SHA-256 已填入。
- [ ] Edge pool、Panel IDs、随机种子和 Probe 算法已冻结。
- [ ] 所有高权重边和扰动已人工审核。
- [ ] 正式模型输出尚未产生。
