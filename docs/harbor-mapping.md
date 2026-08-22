# Harbor 映射

本项目遵循 Harbor 的 `dataset → task → trial → verifier/reward` 结构。

## 1. 先区分 Dataset 根目录和 Task 根目录

仓库根目录是一个 Dataset 项目：

```text
book-reconstruction-benchmark/
├── dataset.toml
├── metric.py
├── tasks/
│   ├── <book-a>/
│   └── <book-b>/
└── templates/book-task/
```

Harbor 不会把 `docs/`、`schemas/` 或整个仓库中的任意子目录都当成 Task。一个单书 Task 的识别边界，是你通过 `-p` 指向的那个目录：

```text
tasks/<book-id>/
├── instruction.md
├── task.toml
├── environment/
│   └── Dockerfile
├── solution/
│   └── solve.sh
└── tests/
    └── test.sh
```

这是 Harbor 官方最小 Task 结构。`environment/`、`solution/` 和 `tests/` 中允许包含额外文件，所以 Book Card、Judge criteria、校准材料和 verifier 代码都可以放在 `tests/` 下。

`templates/book-task/` 具有同样的 Task 根结构，但只是未实例化脚手架：

- 任务名和篇幅仍是占位；
- 私有书稿未加入；
- Oracle 未完成；
- verifier 会明确失败；
- 它没有写入 `dataset.toml`。

因此当前仓库是“Harbor 兼容的 Task scaffold”，不是“已经可以跑榜的 Harbor Task”。

## 2. 运行角色

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

## 3. 概念映射

| Harbor 概念 | 本项目中的含义 |
|---|---|
| Dataset | 整个 Book Reconstruction Benchmark |
| Task | 固定条件下对一本书进行高压缩认知重构 |
| Trial | 一个 Agent 对一本书的一次 Rollout |
| `instruction.md` | 对被测 Agent 公开的任务与篇幅约束 |
| `environment/source/` | 书稿及允许公开给 Agent 的材料 |
| `/app/submission.md` | 单次 Rollout 的主要 Artifact |
| `solution/` | 经审核的 Oracle；不是唯一正确措辞 |
| `tests/gold/` | 隐藏 Book Card、路径、锚点和校准配置 |
| Verifier | 硬约束、证据定位、关系判决、引文复核和图聚合 |
| `reward.json` | 仅包含数值型 reward 字段 |
| 其他 verifier logs | 状态、版本、理由、Judge 明细和错误诊断 |
| `metric.py` | 先对单书和多 Trial 汇总，再跨书宏平均 |

一个 Task 对应一本书，而不是一次随机采样。`-k 3` 为同一本书创建三次 Trial，不复制三个 Task 目录。

## 4. Task 层与模型接入层解耦

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

## 5. 单本书正式 Task 目录

```text
<book-task>/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   └── source/                       # 私有书稿，默认不进 git
├── solution/
│   ├── solve.sh
│   └── reference_submission.md       # Oracle
└── tests/
    ├── Dockerfile                    # separate verifier image
    ├── test.sh
    ├── reward.toml                   # 生产阶段才启用
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

Harbor 只要求根部的 canonical files；上面的额外目录都是 verifier 的依赖文件。

## 6. 为什么使用独立 Verifier 环境

被测 Agent 需要读取私有书稿，但不需要外网。LLM Judge 需要访问模型服务，同时不能让被测 Agent 看到隐藏 Book Card。

因此模板采用：

```toml
artifacts = ["/app/submission.md"]

[environment]
network_mode = "no-network"

[verifier]
environment_mode = "separate"

[verifier.environment]
network_mode = "public"
```

对应行为：

1. Agent 在无网络环境中生成 `/app/submission.md`；
2. Harbor 根据 `artifacts` 把该文件传入独立 verifier 容器，并保持原路径；
3. verifier 镜像从 `tests/Dockerfile` 构建；
4. `tests/Dockerfile` 必须把 `test.sh`、隐藏 Book Card 和评分代码复制到 `/tests/`；
5. Judge 凭据通过 `--ve` 或冻结运行配置注入，不写入仓库。

示例：

```bash
harbor run -p "tasks/<book-id>" \
  -a claude-code \
  -m "<evaluated-model>" \
  --ve ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --ve REWARDKIT_JUDGE="anthropic/<frozen-judge-model>"
```

## 7. Verifier 流程

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
reward.json + audit logs
```

### 7.1 Hard Constraints

程序检查：

- 文件存在；
- 可读且非空；
- 字数；
- 明确格式；
- 可检测的大段复制；
- 超时和任务失败。

### 7.2 Evidence Locator

只寻找 `submission_evidence`，不负责给分。

第一次没有找到时，按冻结规则进行第二次定位或全文复查。Locator 失败不能被悄悄当成模型语义失败。

### 7.3 Relation Adjudicator

读取：

- 冻结关系标准；
- 候选引文与必要上下文；
- `pass_if`、`fail_if`、假阳性和反转模式。

只判断目标关系。可以连接候选文章明确表达的分散命题，不得用原书知识补入缺失桥接命题。

### 7.4 Quote Validator

验证：

- 引文存在；
- 位置正确；
- 上下文没有反转其含义；
- 没有用截断引文掩盖矛盾。

### 7.5 Graph Aggregator

程序根据冻结 Book Card 计算：

- 关系加权覆盖；
- `mandatory` 路径是否完整；
- 每个 `alternative_group` 是否至少有一条完整路径；
- 每个结构的 `path_complete`；
- 全书关系覆盖与核心路径完整率。

Judge 不直接发明总分。

## 8. Harbor Reward 输出约束

Harbor 的 `/logs/verifier/reward.json` 中，每个 value 都必须是整数或浮点数。因此合法输出例如：

```json
{
  "reward": 0.68,
  "cognitive_relation_coverage": 0.68,
  "complete_core_path_rate": 0.31,
  "hard_constraints": 1.0,
  "genericity_failure_rate": 0.14,
  "judge_disagreement_rate": 0.08
}
```

以下内容不能放入 `reward.json`：

```json
{
  "status": "verifier_not_implemented",
  "scoring_contract_version": "cognitive-structure-v1"
}
```

字符串状态、版本、理由、引文和 Judge 明细应写入：

```text
/logs/verifier/verifier-status.json
/logs/verifier/reward-details.json
/logs/verifier/judge-results.jsonl
```

当前 `reward` 仅是 Harbor 兼容字段，开发阶段可暂等于 `cognitive_relation_coverage`；正式排行榜公式尚未冻结。

## 9. 多次 Trial

同一本书的多次 Trial：

- 主结果使用均值；
- 同时报告标准差；
- `best-of-k` 单独报告；
- 被测 Agent 超时、空提交、Verifier 基础设施失败必须区分；
- Judge API 失败不得直接记为被测模型零分；
- 基础设施失败超过冻结阈值时，Trial 标记无效并重跑。

## 10. Dataset Manifest

单个 Task 可以直接运行：

```bash
harbor run -p "tasks/<book-id>" -a oracle
```

要让仓库根目录作为 Dataset 运行，需要把实际 Task 加入 `dataset.toml`：

```bash
harbor add "tasks/<book-id>"
```

这会写入 Task 名称和 digest。当前 `dataset.toml` 的 Task 列表为空，所以运行仓库根目录不会得到正式 Book Task。

## 11. Dataset Metric

每本书先得到：

```text
mean_relation_coverage
mean_complete_core_path_rate
std_relation_coverage
std_complete_core_path_rate
```

再跨书宏平均。不得把所有书的关系叶子池化。

## 12. 当前初始化边界

模板符合 Harbor Task 的最小目录约定，但仍不是正式可跑任务：

- 尚未实例化到 `tasks/<book-id>/`；
- 尚未选择开发书；
- 尚未写入书稿；
- 尚未制作第一份真实认知结构 Rubric；
- 尚未提供经审核 Oracle；
- 尚未实现生产 Locator、Judge 和聚合器；
- 尚未加入 Dataset Manifest；
- 最终单一排行榜分数尚未冻结。

下一里程碑是使用一本合法、结构清楚的开发书完成：

```text
harbor-compatible task root
→ source map
→ cognitive graph
→ Book Card
→ Oracle
→ calibration variants
→ first runnable verifier
→ harbor run -p tasks/<book-id> -a oracle
```
