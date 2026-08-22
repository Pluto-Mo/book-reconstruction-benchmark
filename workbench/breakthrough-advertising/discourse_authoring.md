# 《突破性广告》Discourse Reconstruction Authoring Worksheet（draft）

> 这是构建者与 Human Owner 的审核工作表，不是公开题面。认知正确性只作作者关系边的 content gate，不在篇章维度重复奖励。

## A. 铽接状态

- `book_id`：`breakthrough-advertising-dev`
- 书稿 SHA-256：`e077e6b8467b30b9499a48021a0b360f87c43a2442a0d3a42d420efd74274a3c`
- 当前 Book Card SHA-256：`e25d3605b31af522ea0f98ae98304e93add167fbf644b91c4eea7acf04aad51c`
- 上游基线：`e28d529`
- 书目身份：开发书
- 当前状态：`draft`

语言政策已经按 Human Owner 意见修正：Source Anchor 绑定的是一本书经人工确认的可靠源文件，而不是某种语言。当前双语 OCR 只让这本书多一个互校条件；其他书无须复制该条件。

## B. 新维度到底测什么

本卡不测句式相似、作者感或泛泛流畅度，而分成两部分：

1. `authorial_edge_recovery`：正确内容是否继续承担原书中的控制、转折、边界、案例推论、综合或收束功能，并被后文实际使用。
2. `editorial_coherence`：候选文章重新组织材料后，局部推进、全局顺序、中心线、案例和结尾是否真实成立。

例如“广告不能创造 Mass Desire”和“应选择一个主导欲望”在认知卡里已经判断语义是否正确；篇章卡另问前者是否真的控制后者，而不是两个互不相干的知识点。

Human Owner 进一步澄清：Oracle 编辑时可以参考原作者在文章中自然提出问题、展开解释和回收论点的声音，但“像不像作者”、叙述人称和第三方 / 直接论述口吻都不进入本卡，也不作为 Judge 的独立参照。公开任务只固定中文成文；篇章维度仍只判断关系功能和整体组织。历史广告中的商品主张继续按引用来源判定，不能因任何叙述口吻而变成候选文章认可的事实。

## C. 作者关系边池概览

当前边池共 22 条，其中 14 条暂标 critical。数量与 critical 标记都须经过 Oracle 和受控扰动校准。

| Edge | A → B | 篇章功能 | Stratum | Critical | 进入开发面板 |
|---|---|---|---|---:|---:|
| AE-001 | 反公式 → 第一部分析总路径 | 控制性前提兑现 | global_cross_chapter | 是 | 是 |
| AE-002 | Mass Desire 边界 → 主导欲望选择 | 能力边界重定义策略 | local_argument | 是 | 是 |
| AE-003 | Theme → 三问与 headline entry | 内容与入口的层级 | global_cross_chapter | 否 | 是 |
| AE-004 | 标题下一句职责 → unaware 推进链 | 条件边界展开 | condition_boundary | 是 | 是 |
| AE-005 | Claim 耗竭 → Mechanism / Identification | 市场语言的必要转折 | stance_turn | 是 | 是 |
| AE-006 | 第五 Sophistication → Identification | 失效约束决定新策略 | global_cross_chapter | 是 | 是 |
| AE-007 | Headline → Body | 第一部到第二部的铰链 | global_cross_chapter | 是 | 是 |
| AE-008 | Desire → Intensification | 抽象维度操作化 | local_argument | 否 | 否 |
| AE-009 | 角色价值 → Primary image | 形象选择边界 | condition_boundary | 否 | 是 |
| AE-010 | Primary image / Chesterfield → Believability limits | 反驳直接换人格 | stance_turn | 是 | 是 |
| AE-011 | 既有 belief → belief architecture | 边界转成顺序机制 | local_argument | 是 | 是 |
| AE-012 | TV 接受链 → Gradualization 原理 | 构成性案例到推论 | case_function | 是 | 是 |
| AE-013 | TV Gradualization → TV Redefinition | 同一材料的跨章转读 | global_cross_chapter | 否 | 是 |
| AE-014 | Lifebuoy → Redefinition 区分 | 案例界定反遮掩边界 | case_function | 否 | 是 |
| AE-015 | Sophistication → Mechanization | 市场状态决定机制地位 | global_cross_chapter | 是 | 是 |
| AE-016 | Mechanization → Concentration | 机制成为比较补救证明 | global_cross_chapter | 否 | 否 |
| AE-017 | Attack-only → 完整顾客利益链 | 被拒路线到反驳 | stance_turn | 否 | 是 |
| AE-018 | Fire Injectors → Verification | 比较为 authority proof 准备位置 | case_function | 是 | 是 |
| AE-019 | Belief architecture → Verification | 位置原则的下游兑现 | global_cross_chapter | 是 | 是 |
| AE-020 | Reinforcement / Interweaving → Sensitivity | 局部增强受全局饱和约束 | condition_boundary | 否 | 否 |
| AE-021 | 开篇反公式 → 终章不同 structure | 全书回环 | opening_closure | 是 | 是 |
| AE-022 | 三维教学拆分 → 终章重编织 | 跨章综合 | global_cross_chapter | 是 | 是 |

逐边完整字段、Hard Negatives 与下游依赖见 `discourse_card.draft.json`。

## D. 为什么先拆 Source Anchor

旧认知锚可以支撑“这条关系是否来自原书”，但不一定适合运行时提取一条作者关系边的 A/B 两端。本轮新增 18 个窄锚，重点拆分：

- Identification 定义、市场形象限制、primary-image 规则与 Chesterfield 案例；
- TV Repair Manual 的 setup、agreement、minor adjustments 与 payoff；
- Redefinition 一般机制与 Lifebuoy 案例；
- Concentration 的 attack-only 边界、完整因果链与 Fire Injectors 案例；
- Verification 原理、Fire Injectors authority placement 与 TV proof placement；
- Sensitivity shift points 与终章反公式回环。

这一步不是增加评分点，而是让 Evidence Loader 可以确定地取出边的两端。宽锚继续服务认知来源审计，窄锚服务篇章运行时取证。

## E. 开发面板

- 策略：`stratified_fixed_panels`
- Seed：`20260822`
- 当前面板：`PANEL-DEV-01`
- Edge 数：19
- Rollout：1、2、3
- 所有模型同面板：`true`
- 正式输出后重采样：`false`
- Pairwise A/B 位置反转：`true`
- 覆盖 strata：全部六类

当前只设一个开发面板，是为了先验证全边池的分辨率。Oracle 和成本测试后可以在正式结果产生前版本化缩小，但不能看到模型正式输出后再挑边。

## F. 编辑性连贯探针

### Structure extraction

- 最多 8 个 major units。
- 标题只作信号，不机械等同结构单元。
- 每个单元必须返回字符范围和在中心线中的功能。

### Local progression

- 冻结哈希抽取 8 对相邻段落。
- 每对分别判断 `relation_identifiable`、`forward_dependency`、`advances_argument`。
- 主题相似或连接词出现不能代替依赖。

### Global order

- 抽取 4 对 major units，构造交换版本。
- A/B 位置反转；一胜一负记 `0.5`。
- Judge 依据思想依赖，而不是“前文所述”等表面词。

### Spine connectivity

控制性问题暂定为：

> 面对独特的产品—市场—时机关系，怎样把既存主导欲望导入产品，并按读者状态把最初注意推进为 conviction，而不退化成固定公式？

主要单元若不能说明怎样建立前提、框定问题、提出区分、处理反对、发展机制、限定、应用、综合或收束，就记为 `orphan`。

### Example integration

- 每篇抽查 3 个案例。
- 可接受功能：evidence、counterexample、boundary、turn、application、synthesis。
- 只在定义后附一个故事，移动或删除后论证不受影响，视为装饰。

### Closure

结尾必须同时：回到开头的“独特问题 / 反公式”、依赖正文建立的状态诊断和 belief architecture、并且不能原样替换到普通广告写作文章。

## G. 暂定权重

编辑性连贯内部沿用上游 Pilot 默认：

| Metric | Weight |
|---|---:|
| local_progression | 0.30 |
| global_order | 0.30 |
| spine_connectivity | 0.20 |
| example_integration | 0.10 |
| closure | 0.10 |

篇章维度内部暂定：

| Metric | Weight |
|---|---:|
| authorial_edge_recovery | 0.50 |
| editorial_coherence | 0.50 |

认知维度与篇章维度如何合成最终排行榜分数仍不冻结。

## H. 六类受控扰动

| ID | 只改变什么 | 预期下降 | 原则上稳定 |
|---|---|---|---|
| DP-001 | 交换主要论证单元 | global order | cognitive metrics |
| DP-002 | 抹平因果、转折、边界转场 | local / spine | cognitive metrics |
| DP-003 | 改成定义—案例模块 | local / spine / example | relation coverage |
| DP-004 | 案例内容不变但移到错误位置 | authorial edge / example | cognitive metrics |
| DP-005 | 用通用广告建议替换结尾 | closure | body cognition |
| DP-006 | 只改措辞和表面段落形式 | 不应下降 | 全部实质指标 |

每个扰动都必须由 Human Owner 确认是单变量破坏，才能用于 Judge 资格考试。

## I. Human Owner 下一轮裁决

1. 22 条边里哪些是伪边、重复边或层级过低？
2. 14 条 critical 是否过多；哪些只应留在边池而不进入固定面板？
3. **已通过（2026-08-23）**：TV Repair Manual、Chesterfield、Lifebuoy、Fire Injectors 全部暂时保持 `constitutive + required`。
4. **已通过（2026-08-23）**：先使用单一 19-edge 开发面板制作 Oracle，不提前按模型输出裁边。
5. 8 个 major units、8 对相邻段落、4 对顺序交换、3 个案例抽查怎样随无篇幅、8000、6000、4000、3000 条件保持可比而不因短文样本不足失真？
6. 是否接受先使用上游默认权重，等受控扰动跑完再调权？

这些项目确认前，Discourse Card 保持 `draft`。
