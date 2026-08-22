# Book Reconstruction Benchmark

一个独立的 Harbor benchmark 项目，用来测量模型能否在固定篇幅的整书重构中：

1. 保留一本书真正具有区分力的核心问题、关系和推理路径；
2. 正确区分作者主张、假设、让步、反驳、条件和边界；
3. 保留对结论具有构成作用的案例与论证材料；
4. 避免把作品压缩成正确但无信息量的领域常识。

当前状态：**V1 设计与 Task 脚手架阶段，尚未加入正式书目，也尚未形成可跑榜任务。**

## V1 基准问题

> 给定一本完整的非虚构作品和固定篇幅，模型能否重构作者形成判断时使用的书特异认知结构，而不是只生成一篇流畅的主题摘要？

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
    │   └── book_card.json
    └── cognitive_structure/
        ├── evidence_locator/
        ├── relation_adjudicator/
        ├── quote_validator/
        └── graph_aggregator/
```

最外层五项与 Harbor 官方 Task 结构一致；`tests/`、`solution/` 和 `environment/` 中允许放置额外依赖文件。

`templates/book-task/` 只是上面结构的未实例化脚手架。它目前可以被 Harbor 识别为一个 Task 目录，但会在 verifier 阶段明确失败，因为正式 Book Card、Oracle 和生产 verifier 尚未实现。它也尚未加入 `dataset.toml`。

单独运行一个已实例化 Task：

```bash
harbor run -p "tasks/<book-id>" -a claude-code -m "<model>" -k 3
```

运行整个本地 Dataset：

```bash
harbor run -p "." -a claude-code -m "<model>" -k 3
```

前提是已经通过 `harbor add "tasks/<book-id>"` 把任务写入 `dataset.toml`。

## 核心设计

```text
公开 instruction：目标清楚，不泄露答案
                    ↓
每本书独立的认知结构图
Nodes → Typed Relations → Required / Alternative Paths
                    ↓
证据定位与关系判断分离
                    ↓
LLM Judge 只做冻结的窄语义判断
                    ↓
程序计算关系覆盖和核心路径完整度
                    ↓
每书归一化，再跨书宏平均
```

所有书共享的是：

- 公开任务契约；
- 认知结构 Schema；
- Judge 协议；
- 聚合与失败处理；
- Harbor 和固定 Agent scaffold。

每本书独立拥有：

- 核心认知结构；
- 命题与材料节点；
- 有方向关系；
- 必需路径和替代路径；
- 构成性案例；
- 原书来源锚点；
- `pass_if`、`fail_if` 和校准变体。

V1 Pilot 先并列报告：

- `cognitive_relation_coverage`；
- `complete_core_path_rate`；
- `hard_constraints`。

最终单一排行榜公式需要在开发书、Oracle 和破坏样本试跑后再冻结。

## 项目结构

```text
book-reconstruction-benchmark/
├── dataset.toml
├── metric.py
├── docs/
│   ├── benchmark-v1.md
│   ├── cognitive-structure-contract.md
│   ├── paperbench-adaptation.md
│   ├── rubric-production.md
│   └── harbor-mapping.md
├── schemas/
│   ├── book-card.schema.json
│   ├── evidence-result.schema.json
│   └── judge-result.schema.json
├── scripts/
│   └── validate_book_card.py
├── calibration/
├── configs/
├── tasks/                         # 已实例化、审核通过的 Harbor Tasks
├── results/
└── templates/book-task/           # 未实例化 Task 脚手架
```

## 运行隔离

被测 Agent 使用 `no-network` 环境读取私有书稿。LLM Judge 放在独立 verifier 环境中；`/app/submission.md` 通过 `artifacts` 明确传入，隐藏 Book Card 和 verifier 代码由 `tests/Dockerfile` 打进 verifier 镜像。

Judge 凭据和冻结的 Judge 模型通过 Harbor verifier 环境参数传入，不写入仓库：

```bash
harbor run -p "tasks/<book-id>" \
  -a claude-code \
  -m "<evaluated-model>" \
  --ve ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --ve REWARDKIT_JUDGE="anthropic/<frozen-judge-model>"
```

`/logs/verifier/reward.json` 只能包含数值字段。版本、状态、理由和审计信息必须写入 `reward-details.json`、`verifier-status.json` 或其他日志文件。

## 推荐阅读顺序

1. [V1 基准问题](docs/benchmark-v1.md)
2. [认知结构 Rubric 契约](docs/cognitive-structure-contract.md)
3. [Rubric 生产协议](docs/rubric-production.md)
4. [PaperBench 迁移原则](docs/paperbench-adaptation.md)
5. [Harbor 映射](docs/harbor-mapping.md)

## Book Card 验证

```bash
uv run scripts/validate_book_card.py \
  --card templates/book-task/tests/gold/book_card.example.json \
  --schema schemas/book-card.schema.json
```

该脚本验证 Schema、ID 唯一性、节点/关系/路径交叉引用、构成性案例规则和冻结状态。它不能代替人工确认内容是否忠于原书，也不能代替 Harbor Oracle 运行。

## 隐私与版权

正式书稿默认放在各 Task 的 `environment/source/`，该路径由 `.gitignore` 排除。仓库只保存说明文件、评分卡和可公开材料。公开或发布 Harbor Dataset 前需要单独检查授权。
