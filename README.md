# Book Reconstruction Benchmark

一个独立的 Harbor benchmark 项目，用来测量模型能否在固定篇幅的整书重构中同时做到两件事：

1. **认知结构保留**：保留一本书真正具有区分力的问题、关系、推理路径、立场、条件、边界和构成性材料；
2. **篇章关系重构**：把这些内容重新组织成一篇有中心线、真实推进、材料层级和有效收束的文章，而不是评分点填空或模块化知识笔记。

当前状态：**V1 设计与开发书端到端校准阶段。认知结构和篇章关系两条运行层都已接入一个可由 Harbor 原生解析的开发 Task；Card、Judge、Oracle 和正式标量仍未冻结，因此尚不是正式排行榜任务。**

## V1 基准问题

> 给定一本完整的非虚构作品和固定篇幅，模型能否为一个没有足够时间逐字读完整本书、但仍希望认真理解作者的读者，既重建作者形成判断时使用的书特异认知结构，又把这些内容组织成一篇内部连贯、信息密度高且可以直接阅读的压缩共读文章？

V1 不把“作者感”理解为模仿原作者的句法、词汇或口头禅。新的 `discourse_reconstruction` 维度由两个可审计子分组成：

- `authorial_edge_recovery`：原书重要材料之间的篇章／修辞关系是否被保留；
- `editorial_coherence`：候选文章内部是否形成真实的局部推进、全局顺序、中心线、案例功能和结尾回环。

认知正确性是作者关系边得分的门槛，避免同一内容关系被重复奖励。

## Harbor 目录边界

仓库根目录是 **Dataset 项目目录**，不是单个 Harbor Task。Harbor 真正识别的单书任务根目录应当是：

```text
tasks/<book-id>/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   └── source/                     # 私有书稿，不进 git
├── solution/
│   ├── solve.sh
│   └── reference_submission.md
└── tests/
    ├── Dockerfile                  # separate verifier environment
    ├── test.sh
    ├── gold/
    │   ├── book_card.json
    │   └── discourse_card.json
    ├── cognitive_structure/
    │   ├── evidence_locator/
    │   ├── relation_adjudicator/
    │   ├── quote_validator/
    │   └── graph_aggregator/
    └── discourse_reconstruction/
        ├── authorial_edge_recovery/
        ├── editorial_coherence/
        └── discourse_aggregator/
```

最外层五项与 Harbor 官方 Task 结构一致；`tests/`、`solution/` 和 `environment/` 中允许放置额外依赖文件。

`templates/book-task/` 只是未实例化脚手架。它目前可以被 Harbor 识别为一个 Task 目录，但会在 verifier 阶段明确失败，因为正式 Book Card、Discourse Card、Oracle 和生产 verifier 尚未实现。它也尚未加入 `dataset.toml`。

单独运行一个已实例化的正式 Task：

```bash
harbor run -p "tasks/<book-id>" -a pi -m "<provider>/<model>" -k 3
```

运行整个本地 Dataset：

```bash
harbor run -p "." -a pi -m "<provider>/<model>" -k 3
```

前提是已经通过 `harbor add "tasks/<book-id>"` 把任务写入 `dataset.toml`。

当前开发 Task 的五模型 Pi 矩阵可以直接以路径运行，不需要先加入 Dataset。四个 provider 的非敏感定义冻结在 Task 镜像内；启动器不会读取 `~/.pi/agent`、个人 OAuth、PAT 或当前 shell 中的个人 provider key。仓库和 JobConfig 只保存 Harbor secret 名称：

```bash
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py --print-config
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py \
  --write-hosted-config /tmp/pi-five-models.hosted.json \
  --hosted-task "<org>/<published-task>" \
  --hosted-task-ref "<frozen-ref>"
```

本轮矩阵固定为 GPT‑5.6 sol、Opus 5、Qwen 3.8 Max、K3、DS V4 Pro，Pi 0.84.1，单任务每模型一次、trial 顺序执行。Agent 使用 Harbor 0.22 原生 Pi adapter 的最高档 `xhigh`；Pi 会把 DeepSeek V4 的这一档收敛为官方 `reasoning_effort=max`。其余三组 provider 记录只暴露“是否思考”，没有可审计的分档 effort，因此运行的是各记录可表达的最高模式。Judge 固定为 Qwen 3.8 Max 并开启 Qwen thinking。

路由是硬约束：GPT‑5.6 sol 与 Opus 5 只使用 `openai-benchmark`，Qwen 只使用 `qwen-benchmark`，K3 只使用 `kimi-benchmark`，DS V4 Pro 只使用 `https://api.deepseek.com` 的官方 API。不会读取或回退到个人 OAuth、`opencode-go` 或其他 Pi provider。路由来源和非敏感配置 SHA‑256 会进入预检。

Hosted 运行必须先在 Benchmark 所属 Harbor 组织中独立录入四个 stored secrets；录入过程隐藏输入，值不会进入 task、dataset、JobConfig 或命令行：

```bash
harbor hub secrets add OPENAI_BENCHMARK_API_KEY --org "<benchmark-org>"
harbor hub secrets add QWEN_BENCHMARK_API_KEY --org "<benchmark-org>"
harbor hub secrets add KIMI_BENCHMARK_API_KEY --org "<benchmark-org>"
harbor hub secrets add DEEPSEEK_API_KEY --org "<benchmark-org>"
```

正式 hosted 启动使用已发布的冻结 Task；本地路径不会被 Harbor Hub 自动上传：

```bash
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py \
  --launch \
  --org "<benchmark-org>" \
  --hosted-task "<benchmark-org>/<published-task>" \
  --hosted-task-ref "<frozen-ref>"
```

若只在本机 Docker 上校准，`--run` 必须显式提供一个仓库外、权限为 `0600`、只含四个独立比赛 key 的文件；启动器会清除子进程中的其他 token/key 环境变量。它绝不会自动借用 Pi `auth.json`：

```bash
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py \
  --run --secrets-file "/absolute/path/outside/repository/benchmark-secrets.env"
```

若使用 Harbor 托管基础设施，先运行 `harbor auth login`。本 Benchmark 只选择组织级 stored secrets，不使用会从本机环境取值的 one-off secret 路径。

## 核心设计

```text
公开 instruction：自然的 AI 压缩共读请求，目标清楚但不泄露答案
                    ↓
Book Card：原书认知结构图
Nodes → Typed Relations → Required / Alternative Paths
                    ↓
Discourse Card：作者关系边池 + 冻结面板 + 编辑探针
                    ↓
两条独立评分流水线
Cognitive Structure Pipeline
Discourse Reconstruction Pipeline
                    ↓
程序分别计算细分指标
                    ↓
每书归一化，再跨书宏平均
```

所有书共享：

- 公开任务契约；
- Book Card / Discourse Card Schema；
- Locator、Judge 和受控扰动协议；
- 抽样、位置反转、聚合与失败处理；
- Harbor 和固定 Agent scaffold。

每本书独立拥有：

- 核心认知结构与路径；
- 原书来源锚点；
- 构成性案例；
- 有意义的作者关系边池；
- 分层固定面板；
- 编辑性探针配置和校准扰动；
- `pass_if`、`fail_if`、Hard Negatives 和人工审核记录。

## Instruction 信息充分度

V1 默认公开任务不是“知识杂志编辑委托”，而是一个真实的 AI 助学场景：读者没有足够时间逐字读完整本书，希望 AI 先完整阅读，再生成一篇自己可以直接认真阅读的压缩共读文章。

Instruction 变体按**需求信息充分度**定义，而不是按字数长短定义：

- `natural`：主 Benchmark 条件；自然表达时间约束、学习目的和明显偏好，但不替模型拆解单书答案；
- `explicit`：显式规格消融；把高层质量要求说得更完整，但仍不泄露任何书特异金标准；
- `minimal`：隐含意图诊断；只给用途和少量方向，测试模型自行展开用户需求的能力。

三个条件若用于同一本书，必须是三个彼此隔离的标准 Harbor Tasks，保持书稿、篇幅、Agent scaffold、工具、预算、Verifier、Book Card、Discourse Card、Judge 和聚合不变，只改变各自的 `instruction.md`。`natural` 进入主榜；`explicit` 和 `minimal` 只作为消融／诊断，不与主榜混成一个分数。

详细契约见 [Instruction 信息充分度实验契约](docs/instruction-variants.md)。

V1 Pilot 先并列报告：

- `cognitive_relation_coverage`；
- `complete_core_path_rate`；
- `authorial_edge_recovery`；
- `editorial_coherence`；
- `local_progression`、`global_order`、`spine_connectivity`、`example_integration`、`closure`；
- `hard_constraints`。

`discourse_reconstruction` 可以作为篇章维度内部的诊断性聚合，但认知结构和篇章关系如何合成最终排行榜标量，仍需开发书、Oracle 和破坏样本试跑后冻结。

## 项目结构

```text
book-reconstruction-benchmark/
├── dataset.toml
├── metric.py
├── docs/
│   ├── benchmark-v1.md
│   ├── instruction-variants.md
│   ├── cognitive-structure-contract.md
│   ├── discourse-reconstruction-contract.md
│   ├── paperbench-adaptation.md
│   ├── rubric-production.md
│   ├── harbor-mapping.md
│   ├── runtime-scoring.md
│   ├── semantic-runtime.md
│   └── discourse-semantic-runtime.md
├── schemas/
│   ├── book-card.schema.json
│   ├── discourse-card.schema.json
│   ├── evidence-result.schema.json
│   ├── judge-result.schema.json
│   └── cognitive-aggregate.schema.json
├── scripts/
│   ├── runtime_scoring.py
│   ├── cognitive_semantic_runtime.py
│   ├── discourse_runtime_scoring.py
│   ├── discourse_semantic_runtime.py
│   ├── harbor_cognitive_verifier.py
│   ├── litellm_provider_adapter.py
│   ├── run_pi_benchmark.py
│   ├── compile_cognitive_criteria.py
│   ├── evaluate_cognitive_semantic_runs.py
│   ├── replay_calibration.py
│   ├── validate_book_card.py
│   └── validate_discourse_card.py
├── calibration/
├── configs/
├── tasks/                         # 已实例化的正式或明确标记的开发 Tasks
├── results/
└── templates/book-task/           # 未实例化 Task 脚手架
```

## 运行隔离

Task 的 Agent 基线仍是 `no-network`。Pi 运行配置只在 setup 阶段放行冻结的 Node/npm 主机，并在各 agent.run 阶段仅放行该模型自己的 provider 主机；LLM Judge 放在独立 verifier 环境中。无密钥的 Pi `models.json` 由 Task 镜像提供，API key 只经 Harbor secret 注入。`/app/submission.md` 通过 `artifacts` 明确传入，隐藏 Book Card、Discourse Card 和 verifier 代码由 `tests/Dockerfile` 打进 verifier 镜像。

Judge 凭据和冻结的 Judge 模型通过 Harbor verifier 环境参数传入，不写入仓库。

`/logs/verifier/reward.json` 只能包含数值字段。版本、状态、引用、边面板、位置反转结果、理由和审计信息必须写入其他日志文件。

## 推荐阅读顺序

1. [V1 基准问题](docs/benchmark-v1.md)
2. [Instruction 信息充分度实验契约](docs/instruction-variants.md)
3. [认知结构 Rubric 契约](docs/cognitive-structure-contract.md)
4. [篇章关系重构契约](docs/discourse-reconstruction-contract.md)
5. [Rubric 生产协议](docs/rubric-production.md)
6. [PaperBench 迁移原则](docs/paperbench-adaptation.md)
7. [Harbor 映射](docs/harbor-mapping.md)
8. [认知评分运行契约](docs/runtime-scoring.md)
9. [认知语义运行层](docs/semantic-runtime.md)
10. [篇章语义运行层](docs/discourse-semantic-runtime.md)

## Card 验证

```bash
uv run scripts/validate_book_card.py \
  --card templates/book-task/tests/gold/book_card.example.json \
  --schema schemas/book-card.schema.json

uv run scripts/validate_discourse_card.py \
  --card templates/book-task/tests/gold/discourse_card.example.json \
  --schema schemas/discourse-card.schema.json \
  --book-card templates/book-task/tests/gold/book_card.example.json
```

验证脚本只能检查 Schema、ID、引用、面板、权重和冻结状态，不能代替人工确认内容是否忠于原书，也不能代替 Harbor Oracle 运行。

## 开发期语义运行

当前已经实现认知 Locator/Judge、Quote Validator、Graph Aggregator、Authorial Edge gate/Locator/Judge、结构提取和五类 Editorial Probe。所有总分由程序确定性聚合；模型只裁决冻结的窄问题。Locator 或 Judge 的基础设施失败、弃权和协议错误会把相应运行标为 unscorable，不会变成模型零分。

~~~bash
uv run scripts/replay_calibration.py
python3 -m unittest discover -s scripts -p 'test_*.py'
~~~

静态校准回放仍只用预期关系标签验证确定性认知聚合；真实篇章校准需要提供冻结 Judge 后运行 19 组候选。完整协议见 [认知评分运行契约](docs/runtime-scoring.md)和[篇章语义运行层](docs/discourse-semantic-runtime.md)。

## 隐私与版权

正式书稿默认放在各 Task 的 `environment/source/`，该路径由 `.gitignore` 排除。Discourse Card 只保存 Source Anchor IDs、短摘要和关系说明；正式评分所需的原文短片段在私有 verifier 环境中按 locator 提取。公开或发布 Harbor Dataset 前需要单独检查授权。
