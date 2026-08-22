# Length-Budget Ablation Protocol（draft）

## 1. 结论

篇幅应作为一个受控实验变量，但不应把同一本书复制成五个正式 Harbor Task。

- 正式 Dataset：一本书仍然只有一个 Task，并冻结一个主榜篇幅条件。
- 开发实验：同一 Task 的书稿、Rubric、工具、时限和 Judge 不变，只替换 instruction 中的篇幅句。
- `unconstrained` 与其他篇幅条件单独报告，不混入正式主分。

这样既能测“在不同压缩预算下保留多少认知与篇章结构”，又不会把书目数量和篇幅条件数量混为一谈。

## 2. 条件矩阵

| Condition | 公开篇幅要求 | 作用 | 是否进入主榜 |
|---|---|---|---:|
| `L-unconstrained` | 篇幅不作为评分约束 | 验证 Rubric 上限、Oracle 可达性和完整自然组织 | 否 |
| `L-8000` | 正文不超过 8000 个计数字符 | 低压缩开发点 | 否 |
| `L-6000` | 正文不超过 6000 个计数字符 | 中等压缩候选点 | 否，除非之后被选为主条件 |
| `L-4000` | 正文不超过 4000 个计数字符 | 高压缩压力测试 | 否 |
| `L-3000` | 正文不超过 3000 个计数字符 | 极限优先级与结构损失测试 | 否 |
| `L-main` | 冻结后的窄区间 | 正式跨模型、跨书比较 | 是 |

`L-unconstrained` 不是无限计算：Agent timeout、模型上下文、工具、网络和运行预算仍与其他条件完全相同，只是不以文章字符数判失败。必要的基础设施输出上限只能作为防失控安全边界，不能伪装成评分篇幅。

## 3. 上限与固定篇幅不是一回事

开发曲线使用“最大字符数”，让模型自行决定怎样消费预算；少写是模型策略的一部分。

正式主榜若要测接近固定篇幅的重构，应使用窄区间而不是精确到单字符：

```text
名义 6000 字 → 可考虑 5700–6300
名义 6500 字 → 可考虑 6000–7000
```

当前 `6000–8000` 是较宽的候选开发区间，不能自动视为最终固定篇幅。主条件必须由无篇幅 Oracle、长度曲线、Judge 分辨率和运行成本共同决定，并在保留书正式输出前冻结。

## 4. 唯一允许变化的 Instruction 字段

除以下一句外，公开 instruction 必须逐字保持相同：

其中固定不变的基础语言要求为：

```text
请把原书的核心论证重构为一篇独立的中文文章；正文不使用拉丁字母。历史广告或被引材料的主张仍须清楚保留其引用归属。
```

这是所有长度条件共享的任务合同。作者口吻、叙述人称和风格相似度不评分，也不作为独立参照。长度实验只能替换下列篇幅句，不能同时改变输出语言要求。

### 无评分篇幅约束

```text
正文篇幅不作为本次开发实验的评分约束；仍须写成完整、独立且不过度重复的文章。
```

### 篇幅上限

```text
提交文件的计数字符不超过 {{MAX_CHARS}} 个。
```

### 正式窄区间

```text
提交文件的计数字符为 {{MIN_CHARS}}–{{MAX_CHARS}} 个。
```

不能随篇幅同时改变读者设定、交付形式、提示强度、工具、时间、模型、Rubric、面板、Probe 或 Judge。Agent 必须预先知道预算；事后机械截断不测规划下的压缩能力。

## 5. 计数字符必须程序化冻结

开发计数器现冻结为 `nonwhitespace-codepoints-v1`，实现位于 `scripts/count_submission_chars.py`。它读取整个 UTF-8 提交文件，不做 Unicode normalization，计数所有不属于固定 Unicode `White_Space` 集合的 code points。标题、标点、数字、组合附加符与 Markdown 标记都计入；换行、普通空格、全角空格等固定 White_Space 字符不计入。这样既不需要解释“正文从哪一行开始”，也不能把内容移进标题来规避预算。

开发稿可以另报排除 Markdown 标题行的正文诊断值，但 Hard Constraint 只认整个提交文件的 canonical count。计数器对无效 UTF-8 失败，不自动规范化兼容字、组合字符或零宽字符；同一个字节文件因此总能得到同一个结果。

Hard Constraint 日志至少记录：

- 原始 code-point 数；
- 非空白 code-point 数；
- 是否在条件允许范围内；
- 使用的计数器版本。

本地调用示例：

```bash
python3 scripts/count_submission_chars.py submission.md --max-chars 6000 --pretty
```

开发条件超长只影响 `hard_constraints`，不能让 Judge 自行估算字符数。

## 6. 各条件报告什么

每个长度条件分别报告：

- `cognitive_relation_coverage`；
- `complete_core_path_rate`；
- `authorial_edge_recovery`；
- 五个 editorial 子分；
- `editorial_coherence`；
- Judge 分歧率与运行成本。

主要产物是一组保留曲线：

```text
length budget
→ cognitive relations / complete paths
→ authorial edges / editorial coherence
```

不得把五个长度简单平均成一个主分，也不得为每个模型选择其表现最好的篇幅。AUC、单位千字保留量或最小达标篇幅只能作为后续诊断指标，校准前不进入排行榜。

## 7. 与“不超过 15 个 Task、受限时长”的关系

篇幅条件不增加内容 Task 数，但会直接增加 Trial 数。

若正式 Benchmark 有 15 本书、每书 3 个 Rollout：

```text
一个固定篇幅：15 × 3 = 45 trials / model
五个篇幅条件：15 × 3 × 5 = 225 trials / model
```

五个模型时会从 225 个 Agent trials 增长到 1125 个，还未计入每条认知关系、作者边和编辑探针的 Judge 调用。因此在全部正式书上运行完整五档，会显著放大成本，却不增加书目覆盖面。

推荐分阶段：

1. **Rubric ceiling**：仅开发书运行 `L-unconstrained`，先证明完整答案可达。
2. **Length curve**：仅开发书运行 8000 / 6000 / 4000 / 3000；先做少量 Rollout，再对关键点复跑。
3. **Freeze**：依据 Oracle 可达性、模型分辨率和成本选择一个 `L-main`，在看保留书正式结果前冻结。
4. **Main benchmark**：不超过 15 本书全部只跑 `L-main`，默认 3 Rollout。
5. **External validity ablation**：若预算允许，再选 2–3 本不同领域、不同结构密度的书复跑极端或关键长度，不必把所有书乘五。

## 8. 解释边界

- `L-unconstrained` 高分、短篇幅下降：说明损失来自压缩预算或预算规划。
- `L-unconstrained` Oracle 仍低分：说明 Rubric、篇章边池或 Judge 可能不可达，不能把问题归给篇幅。
- 3000 字 Oracle 无法完成全部路径：它仍可作为 stress test，但不能冒充与正式主任务等价的有效测量。
- 不同长度可能改变模型排序，这本身是有价值的交互效应；应报告曲线，不能混成一个平均名次。
- 同一本书的五个条件共享同一 Book Card 与 Discourse Card；不得按篇幅删关系、改权重或重采样面板。

## 9. 《突破性广告》的当前执行状态

1. 五个 reference 版本均已独立完成：`L-unconstrained = 7177`、`L-8000 = 6362`、`L-6000 = 4186`、`L-4000 = 3051`、`L-3000 = 2646`。四个受限版本均通过各自最大字符数，五版拉丁字母计数均为零。
2. 开发期逐项审计的 reference expectation 均为 `60/60` 条关系、`16/16` 条路径、`19/19` 条面板边和 `4/4` 个构成性案例；短稿中发现并补回的桥接缺口保留在各自 trace 的审计历史中。
3. 机器可读运行清单位于 `length_runs.draft.jsonl`，由 `scripts/validate_length_runs.py` 同时核对文本哈希、计数、上限、拉丁字母和卡片版本；汇总见 `length_curve.draft.md`。
4. Human Owner 尚未逐版确认，Locator、生产 Judge、Panel Judge 与 Probe 也尚未实现或运行。因此当前曲线只证明参考答案可达，不是模型损失曲线，不能据此冻结主榜篇幅。
5. 下一步是在同一开发书上对五个 instruction 条件运行少量同构 Agent trial，再根据实际损失曲线选择窄区间候选；正式 `L-main` 必须在查看保留书结果前冻结。

当前 `book_card.draft.json` 中的 `6000–8000` 保留为早期正式条件候选元数据，不代表已冻结；`L-unconstrained` 和四个上限版本都是开发运行覆盖，不生成另一张 Book Card，也不改变 Discourse Card 链接。
