# Harbor 映射

本项目遵循 Harbor 的 `dataset → task → trial → verifier/reward` 结构。

## 1. Dataset 根目录和 Task 根目录

仓库根目录是 Dataset 项目：

```text
book-reconstruction-benchmark/
├── dataset.toml
├── metric.py
├── tasks/
│   ├── <book-a>/
│   └── <book-b>/
└── templates/book-task/
```

一个正式单书 Task：

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

Book Card、Discourse Card、Judge criteria、校准材料和 verifier 代码都放在 `tests/` 下。

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

首个 Pilot：

```bash
harbor run -p "tasks/<book-id>" -a claude-code -m "<model>" -k 3
```

跨模型比较只替换模型 backend，并冻结书稿、公开任务、Agent scaffold、工具、预算、Book Card、Discourse Card、Judge、面板、探针和失败处理。

## 3. 概念映射

| Harbor 概念 | 本项目中的含义 |
|---|---|
| Dataset | 整个 Book Reconstruction Benchmark |
| Task | 固定条件下对一本书进行整书重构 |
| Trial | 一个 Agent 对一本书的一次 Rollout |
| `instruction.md` | 对 Agent 公开的真实编辑任务与篇幅 |
| `environment/source/` | 私有书稿 |
| `/app/submission.md` | 主要提交 Artifact |
| `solution/` | 经审核 Oracle；不是唯一正确措辞 |
| `tests/gold/book_card.json` | 隐藏认知结构图和路径 |
| `tests/gold/discourse_card.json` | 隐藏作者边池、固定面板和编辑探针 |
| Cognitive Verifier | 证据定位、关系判决、引文复核、图聚合 |
| Discourse Verifier | 作者边判决、文章结构抽取、受控扰动、篇章聚合 |
| `reward.json` | 仅数值型字段 |
| 其他 verifier logs | 状态、版本、引文、边、探针和 Judge 轨迹 |
| `metric.py` | 先汇总多 Trial 和单书，再跨书宏平均 |

## 4. Task 和模型接入解耦

```text
Harbor Task + Verifier（冻结）
                ↑
         固定 Agent scaffold
                ↑
      ┌─────────┼─────────┐
   Model A    Model B    Model C
```

不得因模型不同分叉：

- 公开 instruction；
- 书稿；
- 输出契约；
- 工具；
- Book Card / Discourse Card；
- 抽样面板；
- Judge；
- 聚合。

## 5. 单书正式 Task 目录

```text
<book-task>/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   └── source/                       # 私有书稿，默认不进 git
├── solution/
│   ├── solve.sh
│   └── reference_submission.md
└── tests/
    ├── Dockerfile                    # separate verifier image
    ├── test.sh
    ├── reward.toml                   # 生产阶段启用
    ├── gold/
    │   ├── book_card.json
    │   ├── discourse_card.json
    │   └── calibration/
    ├── hard_constraints/
    ├── cognitive_structure/
    │   ├── evidence_locator/
    │   ├── relation_adjudicator/
    │   ├── quote_validator/
    │   └── graph_aggregator/
    └── discourse_reconstruction/
        ├── authorial_edge_recovery/
        │   ├── source_excerpt_loader/
        │   ├── submission_locator/
        │   ├── edge_adjudicator/
        │   └── position_reversal/
        ├── editorial_coherence/
        │   ├── structure_extractor/
        │   ├── local_progression/
        │   ├── global_order/
        │   ├── spine_connectivity/
        │   ├── example_integration/
        │   └── closure/
        └── discourse_aggregator/
```

## 6. 独立 Verifier 环境

被测 Agent 读取私有书稿但默认不联网。LLM Judge 需要访问模型服务，并且不能把隐藏评分材料暴露给被测 Agent。

```toml
artifacts = ["/app/submission.md"]

[environment]
network_mode = "no-network"

[verifier]
environment_mode = "separate"

[verifier.environment]
network_mode = "public"
```

`tests/Dockerfile` 将 Book Card、Discourse Card、评分代码和 `test.sh` 复制到 `/tests/`。Judge 凭据通过 `--ve` 或冻结运行配置注入。

## 7. Verifier 流程

```text
Agent Rollout
      ↓
/app/submission.md
      ↓
Hard Constraints
      ↓
┌───────────────────────────────┬────────────────────────────────┐
│ Cognitive Structure Pipeline  │ Discourse Reconstruction      │
│                               │ Pipeline                       │
│ Evidence Locator              │ Authorial Edge Recovery        │
│ Relation Adjudicator          │ Editorial Coherence Probes     │
│ Quote Validator               │ Position Reversal / Perturb    │
│ Graph Aggregator              │ Discourse Aggregator           │
└───────────────────────────────┴────────────────────────────────┘
      ↓
reward.json + audit logs
```

### 7.1 Hard Constraints

程序检查文件、可读性、字数、格式、复制率、超时和基础任务失败。

### 7.2 Cognitive Pipeline

认知流水线根据 Book Card 输出：

- `cognitive_relation_coverage`；
- `complete_core_path_rate`；
- 关系和路径审计日志。

### 7.3 Authorial Edge Pipeline

1. 按冻结 Panel IDs 读取作者关系边；
2. 根据 Source Anchor locator 从私有书稿提取必要短片段；
3. 读取关联的认知判决作为 `content_gate`；
4. 在候选文章中定位相关证据；
5. 判断修辞功能和下游依赖；
6. 记录 Edge 结果和分层统计。

不得从所有原书段落对中运行任意随机采样。

### 7.4 Editorial Coherence Pipeline

1. 结构提取器输出中心问题、主要单元、功能和字符范围；
2. 冻结哈希算法选取相邻段落对；
3. 构造主要单元交换版本；
4. Pairwise Judge 执行 A/B 位置反转；
5. 抽查案例功能和开头—结尾回环；
6. 程序计算五个子分及 `editorial_coherence`。

Judge 只判断一个窄探针，不直接给整篇文章“流畅度 1–10 分”。

## 8. Reward 输出

合法示例：

```json
{
  "reward": 0.68,
  "cognitive_relation_coverage": 0.68,
  "complete_core_path_rate": 0.31,
  "authorial_edge_recovery": 0.71,
  "local_progression": 0.74,
  "global_order": 0.50,
  "spine_connectivity": 0.67,
  "example_integration": 0.75,
  "closure": 1.00,
  "editorial_coherence": 0.68,
  "discourse_reconstruction": 0.70,
  "hard_constraints": 1.00,
  "judge_disagreement_rate": 0.08
}
```

当前 `reward` 只是 Harbor 兼容字段，不代表最终排行榜公式已冻结。

以下内容写入其他日志，而不是 `reward.json`：

- Card 和 Prompt 版本；
- Source Anchor 和候选引文；
- Edge IDs 和 Panel IDs；
- 位置反转结果；
- 结构提取和扰动文本；
- Judge 理由、错误和重试。

## 9. 多次 Trial

- 主结果使用均值；
- 同时报告标准差；
- `best-of-k` 单独报告；
- Agent 超时、空提交、Judge API 失败和 verifier 基础设施失败必须区分；
- Judge 失败不能直接记为被测模型 0 分；
- 面板分配规则对所有模型一致。

## 10. Dataset Manifest 和 Metric

实例化 Task 后：

```bash
harbor add "tasks/<book-id>"
```

每本书先得到多 Trial 均值和标准差，再跨书宏平均。不能池化所有认知关系、作者边或编辑探针。

跨书不确定性以书为聚类单位；同一本书的多条边不是多个独立书样本。

## 11. 当前接入边界

模板符合 Harbor Task 最小目录。`tasks/breakthrough-advertising-dev/` 已完成认知和篇章两条开发运行层的原生 Harbor 接入：Agent 使用断网环境，`submission.md` 作为唯一 artifact，Judge 在 separate public verifier 中通过 LiteLLM 调用，并生成 numeric reward 与分离的审计日志。Harbor 的原生边界是 `task.toml`、artifact 生命周期、独立 verifier、`/tests/test.sh` 和 `/logs/verifier/reward.json`；任务专用 Judge 脚本直接实现复杂协议，不额外套 Rewardkit。

该开发 Task 仍不可正式跑榜：

- 本地私有书稿已与 Card 哈希绑定，但不进入仓库或公开 Dataset；
- 没有冻结 Book Card 和 Discourse Card；
- 没有经人工批准并冻结的正式 Oracle；
- 认知 Locator / Judge / Quote Validator / Graph Aggregator，以及 Authorial Edge、结构提取、五类 Editorial Probe 和确定性篇章聚合均已接入开发 Task，但具体 Judge 模型尚未校准和冻结；
- 开发期 Authorial Edge 使用 Book Card 短证据摘要验证接线，正式版本仍需人工确认私有短摘录；
- 19 组篇章校准尚未通过真实冻结 Judge 运行并人工确认；
- 没有加入 Dataset Manifest；
- 跨维度排行榜公式尚未冻结。

下一里程碑：

```text
当前：开发 Card / Oracle / 19 组校准
     + 已实例化的认知和篇章 Harbor Verifier
→ 在可用的 Docker 环境中选定 Judge 模型并运行两条校准
→ 人工确认 Authorial Edge 私有短摘录与篇章校准预期
→ 人工批准并冻结 Card、Oracle、Prompt 和 Provider
→ 加入 Dataset Manifest 并开始正式多 Trial 运行
```
