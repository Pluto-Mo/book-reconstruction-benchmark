# Harbor 映射

本项目遵循 Harbor 的 `dataset → task → trial → verifier/reward` 结构。

## 1. 运行角色

```text
Codex（构建 Benchmark）
          ↓
Harbor（harness / runner / verifier orchestration）
          ↓
固定 Agent scaffold
          ↓
模型 backend
```

首个 Pilot 以 Claude Code 作为固定 Agent scaffold：

```bash
harbor run -p "tasks/<book-id>" -a claude-code -m "<anthropic-model>" -k 3
```

不要把 Codex 当前构建任务当作被测 Agent。

后续跨模型比较必须冻结：

- 同一份书稿和公开 instruction；
- 同一输出文件与篇幅计算；
- 同一 Agent scaffold、系统提示词和工具；
- 同一上下文、时间、token 和采样预算；
- 同一 Book Card、Locator、Judge 和聚合版本；
- 同一 Rollout 和失败处理规则。

只替换模型 backend。若不同模型使用不同 scaffold，结果只能解释为 Agent 系统比较。

## 2. 概念映射

| Harbor 概念 | 本项目中的含义 |
|---|---|
| Dataset | 整个 Book Reconstruction Benchmark |
| Task | 固定条件下对一本书进行一次高压缩认知重构 |
| Trial | 一个 Agent 对一本书的一次 Rollout |
| `instruction.md` | 对被测 Agent 公开的任务与篇幅约束 |
| `environment/source/` | 书稿及允许公开给 Agent 的材料 |
| `/app/submission.md` | 单次 Rollout 的主要 Artifact |
| `solution/` | 经审核的 Oracle；不是唯一正确措辞 |
| `tests/gold/` | 隐藏 Book Card、路径、锚点和校准配置 |
| Verifier | 硬约束、证据定位、关系判决、引文复核和图聚合 |
| `reward.json` | 临时兼容标量、并列主指标与审计诊断 |
| `metric.py` | 先对单书和多 Trial 汇总，再跨书宏平均 |

一个 Task 对应一本书，而不是一次随机采样。`-k 3` 为同一本书创建三次 Trial，不复制三个 Task 目录。

## 3. 任务层与模型接入层解耦

```text
Harbor Task + Verifier（冻结）
                ↑
         固定 Agent scaffold
                ↑
      ┌─────────┼─────────┐
   Model A    Model B    Model C
```

不因模型不同而分叉：

- 公开 instruction；
- 书稿；
- 文件契约；
- 工具；
- Book Card；
- Judge；
- 聚合。

## 4. 单本书任务目录

```text
<book-task>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   └── source/                       # 私有书稿，默认不进 git
├── solution/
│   ├── solve.sh
│   └── reference_submission.md       # Oracle
└── tests/
    ├── test.sh
    ├── reward.toml
    ├── gold/
    │   ├── book_card.json
    │   └── calibration/
    ├── hard_constraints/
    └── cognitive_structure/
        ├── evidence_locator/
        ├── relation_adjudicator/
        ├── quote_validator/
        └── graph_aggregator/
```

## 5. Verifier 流程

本项目不需要 PaperBench 的代码 Reproduction 阶段。提交物是静态 Markdown：

```text
Agent Rollout
      ↓
/app/submission.md
      ↓
Hard Constraints
      ↓
Evidence Locator
      ↓
Relation Adjudicator
      ↓
Quote Validator
      ↓
Graph Aggregator
      ↓
reward.json
```

### 5.1 Hard Constraints

程序检查：

- 文件存在；
- 可读且非空；
- 字数；
- 明确格式；
- 可检测的大段复制；
- 超时和任务失败。

### 5.2 Evidence Locator

只寻找 `submission_evidence`，不负责给分。

第一次没有找到时，按冻结规则进行第二次定位或全文复查。Locator 失败不能被悄悄当成模型语义失败。

### 5.3 Relation Adjudicator

读取：

- 冻结关系标准；
- 候选引文与必要上下文；
- `pass_if`、`fail_if`、假阳性和反转模式。

只判断目标关系。可以连接候选文章明确表达的分散命题，不得用原书知识补入缺失桥接命题。

### 5.4 Quote Validator

验证：

- 引文存在；
- 位置正确；
- 上下文没有反转其含义；
- 没有用截断引文掩盖矛盾。

### 5.5 Graph Aggregator

程序根据冻结 Book Card 计算：

- 关系加权覆盖；
- `mandatory` 路径是否完整；
- 每个 `alternative_group` 是否至少有一条完整路径；
- 每个结构的 `path_complete`；
- 全书关系覆盖与核心路径完整率。

Judge 不直接发明总分。

## 6. Pilot Reward 输出

```json
{
  "reward": 0.68,
  "cognitive_relation_coverage": 0.68,
  "complete_core_path_rate": 0.31,
  "hard_constraints": 1.0,
  "genericity_failure_rate": 0.14,
  "judge_disagreement_rate": 0.08,
  "scoring_contract_version": "cognitive-structure-v1"
}
```

当前 `reward` 仅为 Harbor 兼容字段，开发阶段暂等于 `cognitive_relation_coverage`。正式排行榜公式尚未冻结。

以下字段不应被混入质量分：

- Judge 置信度；
- Judge 分歧率；
- Locator 重试次数；
- Verifier 延迟。

它们用于诊断评分可靠性。

## 7. 多次 Trial

同一本书的多次 Trial：

- 主结果使用均值；
- 同时报告标准差；
- `best-of-k` 单独报告；
- 被测 Agent 超时、空提交、Verifier 基础设施失败必须区分；
- Judge API 失败不得直接记为被测模型零分；
- 基础设施失败超过冻结阈值时，Trial 标记无效并重跑。

## 8. Dataset Metric

每本书先得到：

```text
mean_relation_coverage
mean_complete_core_path_rate
std_relation_coverage
std_complete_core_path_rate
```

再跨书宏平均。不得把所有书的关系叶子池化。

## 9. 当前初始化边界

模板仍不是正式可跑任务：

- 尚未选择开发书；
- 尚未写入书稿；
- 尚未制作第一份真实认知结构 Rubric；
- 尚未提供经审核 Oracle；
- 尚未实现生产 Locator、Judge 和聚合器；
- 最终单一排行榜分数尚未冻结。

下一里程碑是使用一本合法、结构清楚的开发书完成：

```text
source map
→ cognitive graph
→ Book Card
→ Oracle
→ calibration variants
→ first runnable verifier
```
