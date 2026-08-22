# 《突破性广告》Rubric Authoring Worksheet（draft）

> 这是构建者工作表，不是被测 Agent 的公开题面。所有内容都等待 Human Owner 审核。

## A. 书稿与任务

- `book_id`：`breakthrough-advertising-dev`
- 书名：Eugene M. Schwartz, *Breakthrough Advertising* / 《突破性广告》
- 书稿 SHA-256：`e077e6b8467b30b9499a48021a0b360f87c43a2442a0d3a42d420efd74274a3c`
- 固定篇幅：Human Owner 同意暂定 `6000–8000` 个中文字符；须由 Oracle 满分可达性验证后再冻结
- 定位方案：`BA-<sha12>-<chapter>-src-<kind>-L<start>-L<end>`；`src` 是语言中立的源文件行空间
- 书目身份：开发书候选，不进入正式主榜
- 人工负责人：待填写
- 输出语言：重构为独立中文文章，正文不夹拉丁字母。Oracle 编辑时可参考原作者自然展开论证的声音，但候选答案不以口吻相似度评分，也不把某一种叙述人称设为硬约束；历史广告的商品主张仍须保持引用归属。

## B. 全书问题意识

作者反复处理的中心问题不是“怎样写漂亮标题”，而是：

> 面对每一次独特的产品—市场—时机关系，如何识别市场中已经存在的大众欲望，把它聚焦到一个产品最有销售力的功能性满足方式上；再按受众的 Awareness 与 Sophistication 选择进入点，并通过 Desire、Identification 与 Belief 的结构化编排，把最初兴趣推进为对产品能够兑现承诺的 conviction。

全书的上位依赖可暂写为：

```text
独特问题 → 分析而非套公式
          ↓
既存 Mass Desire + 主导 Functional Performance
          ↓
Theme
          ↓
Awareness × Sophistication → Headline entry
          ↓
Body copy：Desire + Identification + Belief
          ↓
Gradualization / Redefinition / Mechanization /
Concentration / Camouflage + Verification
          ↓
Reinforcement / Interweaving / Sensitivity
          ↓
Conviction → action
```

一个只知道广告常识、没有读过本书的人，最容易把它压缩成：“了解用户需求，突出利益，用吸睛标题、故事、证明、社会认同和竞品对比建立信任。”这句话主题正确，但删除了本书的诊断变量、状态转移、方向关系、接受链和边界。

## C. 候选核心认知结构

| ID | 结构 | 中心问题 | 暂定权重 | 删除后的损失 |
|---|---|---|---:|---|
| CS-01 | 独特问题与分析式创意 | 为什么不能复用成功公式，广告 theme 应怎样产生？ | 1.0 | 会把本书误成标题模板库 |
| CS-02 | 既存大众欲望与主导产品表现 | 文案能改变什么、不能创造什么，如何把欲望接到产品？ | 1.0 | 会把 Mass Desire 退化成“洞察需求” |
| CS-03 | Awareness × Sophistication 的标题入口 | 两个市场状态怎样共同改变标题策略？ | 1.0 | 会丢失全书最具区分力的状态模型 |
| CS-04 | 三维心智、正文与 Intensification | 标题之后，正文怎样把兴趣推进成 conviction？ | 1.0 | 会把第二部误成十三招或写作清单 |
| CS-05 | Identification 与可信形象桥 | 产品怎样既满足功能又成为角色表达？ | 1.0 | 会把 Identification 误成证明、代言或泛品牌人格 |
| CS-06 | Gradualization 与 Redefinition | 怎样从既有信念走到原本不接受的结论，并移除内置阻力？ | 1.0 | 会丢失接受链、顺序力量与视角重排 |
| CS-07 | Mechanization、Concentration、Camouflage | 怎样回答“如何做到”、处理替代方案并借用媒介信任？ | 1.0 | 会把三种机制混成“给证据、打竞品、像新闻” |
| CS-08 | Verification 与整体编织 | 分析出的元素怎样按读者状态重新组成一个完整广告？ | 1.0 | 会把七种技术误成固定线性配方 |

当前全部等权。提高任何权重前，需说明它提升的是全书理解的重要性，而不是制作难度或个人偏好。

## D. 候选构成性案例

| 案例 | 暂定功能 | 为什么可能不可替换 | Human Owner 决策 |
|---|---|---|---|
| TV Repair Manual | Gradualization + Simplification | 作者逐句拆出从共同怨气、agreement、TV 可靠、minor adjustments 到节省维修费的完整 acceptance chain，并跨章复用 | `constitutive + required` 已批准（2026-08-23） |
| Chesterfield “Blow Some My Way” | Identification bridge | 完整演示保留不利 primary image、降低强度、用它桥接到新认同 | `constitutive + required` 已批准（2026-08-23） |
| Lifebuoy / B.O. | Redefinition | 完整演示不可移除的缺点如何在不否认事实的情况下变成 benefit proof | `constitutive + required` 已批准（2026-08-23） |
| Fire Injectors vs spark plugs | Concentration | 完整演示竞品弱点、对读者损害与本品消除之间的一一对应 | `constitutive + required` 已批准（2026-08-23） |

Rinso、减肥标题演变、烟草市场、Wall Street Journal 改版等当前保留为重要说明材料或校准候选，不先一律标成构成性案例。

## E. 明确排除或降权的内容

- 第四章 38 种标题强化方式：作为可替换表达库，不逐项建成 38 个高权重叶子。
- 第七章十三种强化形式：评分“同一主导欲望通过新鲜具体图景被强化、而非重复”的机制，不要求十三项全用。
- 大量广告标题、品牌名、数字、医学或烟草效果：除非承担构成性路径，否则只是说明材料。
- 尾声书目：不进入核心认知图。
- 纯句式、节奏或作者修辞模仿：V1 不计分。
- 作者口吻、叙述人称及“像不像原作者”：V1 不计分，也不作为独立 Judge 参照；不能以此惩罚语义与结构均正确的第三方或其他自然组织方式。
- Mood：只在“语气须隐性且匹配目标受众”改变可信度边界时作为诊断参考；不把形容词数量或文风模仿纳入主分。
- 历史案例中的有害或过时主张：只评分正确归属于作者/被引广告及其论证功能，不要求候选文章认同其真实性或价值立场。

## F. 常识化陷阱

1. 写成“广告创造需求”，反转作者的 Mass Desire 主张。
2. 写成“突出 feature/benefit”，省略物理事实从属于功能性主表现以及单一主导项的选择。
3. 把 Awareness 与 Sophistication 合并成一个“用户成熟度”。
4. 说“标题要把卖点说清楚”，删除“标题只负责让人读下一句”的边界。
5. 说“市场越成熟，承诺越强”，反转第三阶段从 `what` 转到 `how/mechanism` 的换位。
6. 只列 Desire / Identification / Belief 三个词，不保留各自功能和汇合为 conviction 的关系。
7. 把 Identification 写成用户评价、权威背书、社会证明或随意替换品牌人格。
8. 把 Gradualization 写成“循序渐进解释”或“多给证据”，省略从已接受事实到目标结论的结构和顺序。
9. 把 Redefinition 写成否认产品缺点；作者要求保留事实并重排视角。
10. 把 Mechanization、Documentation、Verification 当作同义词。
11. 把 Concentration 写成攻击或抹黑竞品，省略“弱点 → 对读者损害 → 本品消除”。
12. 把 Camouflage 写成“伪装成新闻”，省略特定媒介信任、风格和受众之间的条件性迁移。
13. 把七种技术按固定次序全塞入文案，反转“每个问题需要不同结构”和 sensitivity 的主张。

## G. Human Owner 必须先裁决

1. **已通过（2026-08-22）**：上述八个一级结构边界全部保留。
2. **已修订（2026-08-23）**：第一阶段先制作无评分篇幅约束 Oracle；随后运行 8000 / 6000 / 4000 / 3000 字上限消融。`6000–8000` 仅保留为正式主榜候选区间。
3. **已否决原方案（2026-08-22）**：不能把英文 OCR 设成跨书主锚规则。改用语言中立、按书确认可靠来源的定位政策；本书双语内容只作互校条件。
4. **已通过（2026-08-23）**：TV Repair Manual、Chesterfield、Lifebuoy、Fire Injectors 四例均暂定 `constitutive + required`，进入 Oracle 与破坏样本验证。
5. **已修订（2026-08-23）**：本书输出固定为中文成文；Oracle 编辑时尽量保持原作者自然论述的声音，但作者口吻、叙述人称和风格相似度不进入 Rubric、Judge 或硬约束。
6. `mass desire cannot be created`、`belief is immutable` 等应作为“作者的理论断言”忠实重构，是否接受带时间尺度的限定性改写？
7. **开发草案已实现，待确认**：Fire Injectors 的技术效果必须归于被分析的历史广告主张，不能写成作者或基准认可的工程事实；作者对其他竞争策略“可选择或拒绝、并非推荐”的更广立场边界仍待裁决。
8. 是否同意先全部等权，再让 Oracle、语义等价改写和受控破坏样本决定调权？
9. 这本书是否只作开发书，不进入将来的正式主榜？

## H. 当前尚未执行

- Rubric Auditor 对每条认知关系的独立问题清单。
- Discourse Card 作者边池、固定面板和编辑探针的 Human Owner 审核。
- Red-Team 的 12 类单变量破坏样本。
- 无评分篇幅约束 Oracle、第二种语义等价组织，以及 8000 / 6000 / 4000 / 3000 字独立重写版本。
- Evidence Locator、Relation Adjudicator 和 Quote Validator 的冻结 criteria。
- Judge 资格考试与路径分辨率测试。
- Human Owner 审核、`human_reviewed` 或 `frozen` 状态。
