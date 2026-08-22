# 《突破性广告》开发校准集

当前落盘三条正向锚和十六条负向变体。每个 case 同时登记在 `cognitive/` 与 `discourse/`，以便检查目标维度下降和非目标维度的误伤；6000 / 4000 / 3000 reference 属于长度实验条件，另记在工作台的 `length_runs.draft.jsonl`，不伪装成认知或篇章扰动。

| Case | 唯一改动 | 认知预期 | 篇章预期 |
|---|---|---|---|
| `BA-CAL-BASE-001` | 无，开发基准 | reference ceiling | reference ceiling |
| `BA-CAL-POS-001` | 语义保持改写 | 60/60，16/16 | 19/19，编辑探针稳定 |
| `BA-CAL-NEG-C-001` | 把“旧标题会失效”反转为“仍然奏效” | 仅 `R-03-05`、`P-03-01` 失败 | 19/19 边稳定；局部推进因内在矛盾未冻结 |
| `BA-CAL-NEG-X-001` | 删除救生圈案例中“药味与清洁力不可分”的前提 | 仅 `R-06-10`、`P-06-03` 失败 | 仅 `AE-014` 失败；案例整合探针因抽样未冻结 |
| `BA-CAL-NEG-D-001` | 完整交换第五、六 major sections | 60/60，16/16 | 仅 `AE-018` 失败；`global_order` 下降 |
| `BA-CAL-NEG-CASE-001` | 整案删除切斯特菲尔德 | 仅 `R-05-06`、`P-05-02` 失败 | 仅 `AE-010` 失败；案例整合未冻结 |
| `BA-CAL-NEG-CASE-002` | 整案删除电视维修手册 | `R-06-04/05/06`、`P-06-02` 失败 | `AE-012/013` 失败；案例整合未冻结 |
| `BA-CAL-NEG-CASE-003` | 整案删除救生圈 | 仅 `R-06-10`、`P-06-03` 失败 | 仅 `AE-014` 失败；案例整合未冻结 |
| `BA-CAL-NEG-CASE-004` | 整案删除火焰喷射器 | 仅 `R-07-07`、`P-07-02` 失败 | 仅 `AE-018` 失败；案例整合未冻结 |
| `BA-CAL-NEG-D-002` | 把四处因果或跨章回收铰链改成并列转场 | 60/60，16/16 | 无确定失败边；`AE-001/015/019` 与两项连接探针暂不冻结 |
| `BA-CAL-NEG-D-003` | 把电视维修案例移成终章前的独立模块 | 60/60，16/16 | `AE-012/013` 失败；局部推进与中心线连接下降 |
| `BA-CAL-NEG-D-004` | 把火焰喷射器比较段插进电视案例推理链 | 60/60，16/16 | `AE-018` 失败；局部推进与中心线连接下降 |
| `BA-CAL-NEG-D-005` | 用同领域通用检查表替换正文依赖的回环结尾 | 60/60，16/16 | `AE-021` 与 `closure` 失败 |
| `BA-CAL-NEG-C-002` | 保留电视案例的省钱结论，删除产生它的接受链 | `R-06-04/05/06`、`P-06-02` 失败 | `AE-012/013` 失败；局部推进与案例抽样未冻结 |
| `BA-CAL-NEG-C-003` | 用“讲清楚、讲生动”替代机制呈现的三条件映射 | 仅 `R-07-02`、`P-07-01` 失败 | 仅 `AE-015` 失败；五项编辑探针稳定 |
| `BA-CAL-NEG-C-004` | 保留三维及确信术语，删除标题—正文接力和三维汇合 | `R-04-01/02`、`P-04-01` 失败 | 仅 `AE-007` 失败；局部推进抽样未冻结 |
| `BA-CAL-POS-002` | 将七个平级标题重组为“诊断—说服—编排”三层标题树，正文不动 | 60/60，16/16 | 19/19；全局次序与中心线探针待结构提取器冻结 |
| `BA-CAL-NEG-C-005` | 把历史广告的火焰喷射器技术宣称升级为已证实工程事实 | 仅 `R-07-07`、`P-07-02` 失败 | 19/19，五项编辑探针稳定 |
| `BA-CAL-NEG-C-006` | 删除第一熟化阶段的“直接主张—正文证明”条件映射 | 仅 `R-03-06`、`P-03-02` 失败 | 19/19；局部推进抽样未冻结 |

十六个负样本与一份正确重组对照不是手工复制后随意改写。`mutations/*.json` 绑定 L-8000 正向锚的 SHA-256，并声明精确字符串替换、完整块交换、原文块移动或标题层级重组；`scripts/materialize_calibration_variants.py` 生成工作台 `perturbations/` 中的文本，同时冻结输出哈希与 canonical count。这样可以审计“究竟只改了什么”。整案删除可能包含多处同步替换，但这些操作共同实现一个语义变量：删除该案例及其跨章回收，同时保留一般原则。抽样尚未冻结或证据不足以二值化的结果显式进入 `expected_unfrozen_*`，不计作预先认定的失败。

所有条目仍为开发状态：

- Book Card 与 Discourse Card 均为 `draft`；
- Judge Prompt 与生产 Verifier 尚未实现；
- 十六份负样本和一份正确重组对照的精确边界已经 Agent 独立审计，但仍只是预期标签来源；
- `human_confirmation.status = pending` 的条目不能用于冻结。

文本不复制到本目录；`text_path` 指向工作台中的版本化草稿。正式 Task 冻结前必须把文本、mutation spec、卡、面板、Prompt 和预期标签绑定到不可变哈希。

开发期验证：

```bash
python3 scripts/materialize_calibration_variants.py calibration/books/breakthrough-advertising/mutations/*.json --check --pretty
python3 scripts/validate_calibration.py calibration/books/breakthrough-advertising \
  --book-card workbench/breakthrough-advertising/book_card.draft.json \
  --discourse-card workbench/breakthrough-advertising/discourse_card.draft.json \
  --pretty
```
