# 《突破性广告》Source Map（draft）

## 文档身份

- SHA-256：`e077e6b8467b30b9499a48021a0b360f87c43a2442a0d3a42d420efd74274a3c`
- 总行数：`9867`
- 形式：中文 OCR 主体后接英文 OCR 主体，不是逐页双语对照。
- 定位原则：所有锚点使用同一哈希绑定文档的绝对行空间；语言不构成主锚等级。
- 双语用途：两个文本见证只用于本书的 OCR 互校。其他单语书直接使用各自经人工确认的可靠来源，不能把本书的双语形态推广成 Benchmark 规则。

定位与该 SHA-256 绑定。书稿字节发生变化后，本 Source Map 和 Book Card 自动失效。

## 定位格式

```text
BA-e077e6b8467b-<chapter>-src-<kind>-L<start>-L<end>
```

示例：

```text
BA-e077e6b8467b-C03-src-main-L5776-L6043
BA-e077e6b8467b-C03-src-parallel-check-L1049-L1326
```

`src` 只表示这一份源文档的行空间，不表示英文、中文或任何版本优先。细粒度 `source_anchor.locator` 使用同一前缀，并把范围缩到支撑该节点或关系的最小稳定行区间。广告样本重复出现时加 `occ1`、`occ2`，不得只用广告标题定位。

## 章节范围

| ID | 中文范围 | 英文范围 | 规范标题 / 备注 |
|---|---:|---:|---|
| FRONT | L23–L290 | L4698–L5103 | 英文含 Boardroom 版新增前言；不与中文完全平行 |
| C01 | L291–L486 | L5104–L5253 | Mass Desire |
| C02 | L487–L1048 | L5254–L5775 | State of Awareness |
| C03 | L1049–L1326 | L5776–L6043 | Market Sophistication |
| C04 | L1327–L1562 | L6044–L6289 | 38 Ways / Verbalization；英文 OCR 漏章号 |
| C05 | L1563–L1716 | L6290–L6435 | Creative Planning；英文 OCR 漏章号 |
| C06 | L1717–L1798 | L6436–L6510 | Inside Your Prospect's Mind；英文标题 OCR 损坏 |
| C07 | L1799–L2304 | L6510–L7009 | Intensification |
| C08 | L2305–L2638 | L7010–L7353 | Identification；中文“鉴定证明”偏义 |
| C09 | L2639–L3084 | L7354–L7805 | Gradualization；英文标题 OCR 为 `GRADUALEATION` |
| C10 | L3085–L3318 | L7806–L8051 | Redefinition |
| C11 | L3319–L3504 | L8052–L8243 | Mechanization |
| C12 | L3505–L3712 | L8244–L8449 | Concentration；英文正文漏主标题，中文“浓缩精华”偏义 |
| C13 | L3713–L4168 | L8450–L8781 | Camouflage |
| C14 | L4169–L4648 | L8782–L9830 | The Final Touches；英文正文漏独立章题 |
| EPILOGUE | L4649–L4684 | L9831–L9867 | Copy Writer's Library |
| TRAILING | L4685–L4697 | — | 中文封底 / ISBN OCR 残片，排除正文 |

## 细粒度语义锚

| Anchor | 当前工作行范围 | 论证功能 |
|---|---:|---|
| SA-001 | L4855–L4871 | 反公式、分析法与“每个问题独特” |
| SA-002 | L6294–L6324 | 替词、公式与分析式创意的区分 |
| SA-003 | L6398–L6434 | 第一部总括：市场分析 + 产品分析 → theme → headline → conviction |
| SA-004 | L5104–L5134 | 大众欲望已存在，广告只导流；Amplification / education 边界 |
| SA-005 | L5160–L5180 | 主导欲望三维与标题桥梁 |
| SA-006 | L5188–L5214 | 物理产品与功能产品的从属关系 |
| SA-007 | L5218–L5250 | 单一主导 performance 与其余材料的支持角色 |
| SA-008 | L5266–L5298 | Mass Desire / Awareness / Sophistication 三问与标题真实职责 |
| SA-009 | L5404–L5456 | 新产品、已知欲望与已知需要的不同进入路径 |
| SA-010 | L5492–L5534 | 完全不知情市场的 identification → problem → solution → product 路径 |
| SA-011 | L5776–L5854 | Sophistication 第一、二阶段及可信度耗竭 |
| SA-012 | L5856–L5944 | 第三至第五阶段：机制前置、机制扩张、转向 identification |
| SA-013 | L6442–L6508 | 正文销售、三维心智与 conviction |
| SA-014 | L6512–L6556 | Intensification：新鲜具体图景强化，而非重复 |
| SA-015 | L7010–L7150 | Identification 的双重购买理由、角色和边界 |
| SA-016 | L7178–L7246 | Primary image 的保留、降强度与桥接 |
| SA-017 | L7286–L7308 | Believability bridge 与不可跨越的形象鸿沟 |
| SA-018 | L7354–L7420 | Desire / Identification / Belief 汇合与 Gradualization 定义 |
| SA-019 | L7430–L7470 | Statement 内容 + 前置准备；Awareness 重新定义为 readiness to accept |
| SA-020 | L7472–L7630 | TV Repair Manual 的完整 acceptance chain |
| SA-021 | L7634–L7652 | 延迟结论、逐层 agreement 和 believability structure 总结 |
| SA-022 | L7806–L7846 | Redefinition 定义与 Lifebuoy liability → asset 案例 |
| SA-023 | L7850–L7910 | TV Repair Manual 的 Simplification / “repair”重定义 |
| SA-024 | L7912–L8008 | Simplification、Escalation、Price Comparison 三种分支 |
| SA-025 | L8046–L8048 | Gradualization 是事实顺序；Redefinition 是视角重排 |
| SA-026 | L8074–L8104 | 读者的 information / proof / mechanism 三种需求与 verbal proof |
| SA-027 | L8106–L8204 | Mechanism 的 name / describe / feature 条件分支 |
| SA-028 | L8246–L8296 | Concentration：竞品弱点 → 对读者损害 → 本品消除 |
| SA-029 | L8450–L8488 | Camouflage：媒介信任与形式/措辞的条件性迁移 |
| SA-030 | L8782–L8800 | 终章总目标：将分解元素重新编织成整体 |
| SA-031 | L8802–L8880 | Documentation / Mechanization / Verification 的区分与 proof placement |
| SA-032 | L8882–L8978 | Reinforcement 与 Interweaving |
| SA-033A | L8980–L8998 | Sensitivity 与 reader-driven shift points |
| SA-033B | L9396–L9424 | “每个问题需要不同结构”及 opening-to-closure 回环 |
| SA-034 | L9767–L9829 | Mood 的隐性受众适配；主要作为 V1 范围边界参考 |

当前工作锚多位于文档的英文半部，因为该部分在关键术语处更易核对；这只是本书草案的取证选择，不是语言优先的评分政策。

### 为篇章关系边新增的窄锚

| Anchor | 当前工作行范围 | 论证功能 |
|---|---:|---|
| SA-015A | L7010–L7048 | Identification 的第二重购买价值 |
| SA-015B | L7140–L7158 | 市场接受度对角色形象的限制 |
| SA-016A | L7178–L7218 | Primary image 一般规则 |
| SA-016B | L7220–L7246 | Chesterfield 的形象桥接案例 |
| SA-020A | L7472–L7494 | TV 案例起点与延迟结论 |
| SA-020B | L7494–L7546 | Agreement 到电视可靠 |
| SA-020C | L7548–L7602 | 可靠到 minor adjustments |
| SA-020D | L7604–L7630 | 知识与节省维修费 payoff |
| SA-022A | L7806–L7830 | Redefinition 一般机制 |
| SA-022B | L7830–L7846 | Lifebuoy / B.O. 构成性案例 |
| SA-028A | L8282–L8288 | Attack-only 失败边界 |
| SA-028B | L8288–L8296 | Concentration 完整因果链 |
| SA-028C | L8298–L8374 | Fire Injectors 逐点比较案例 |
| SA-031A | L8802–L8842 | Verification 与 proof placement 原则 |
| SA-031B | L8844–L8856 | Fire Injectors authority placement |
| SA-031C | L8862–L8880 | TV proof placement 与三种 proof 区分 |

除仅作范围边界的 SA-034 外，上述锚点均进入当前 Book Card。宽锚用于认知关系的章节级支撑；窄锚用于作者关系边的 A/B 提取，二者不得在运行时混用。

## OCR 与版本风险

- 两个 OCR 文本见证都有 `copv`、`MEND`、`GRADUALEATION`、断字、术语漂移和数字误识别；不得把精确拼写当评分要求。
- 中文把 `Identification` 误导性地译为“证明”，把 `Gradualization` 译作“递增信任”，把 `Concentration` 译作“浓缩精华”。关系定义须综合对应上下文、另一文本见证及人工原版核验，不能按任一 OCR 词面自动裁断。
- 英文 FRONT 含中文部分没有的 Boardroom 版材料。当前核心结构不依赖该新增前言。
- 历史广告中的产品效果、医疗、烟草、性别或社会地位主张，只记录作者如何使用材料，不把它们当作 Benchmark 认可的现实事实。
- 冻结前应以可靠原版复核所有高权重关系、构成性案例和疑似 OCR 数字；这个要求按书稿可靠性执行，与来源语言无关。
