# Book Reconstruction Benchmark

一个独立的 Harbor benchmark 项目，用来测量模型能否在固定篇幅的整书重构中：

1. 保留一本书真正具有区分力的核心问题、关系和推理路径；
2. 正确区分作者主张、假设、让步、反驳、条件和边界；
3. 保留对结论具有构成作用的案例与论证材料；
4. 避免把作品压缩成正确但无信息量的领域常识。

当前状态：**V1 设计与脚手架阶段，尚未加入正式书目，也尚未形成可跑榜任务。**

## V1 基准问题

> 给定一本完整的非虚构作品和固定篇幅，模型能否重构作者形成判断时使用的书特异认知结构，而不是只生成一篇流畅的主题摘要？

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
├── tasks/
├── results/
└── templates/book-task/
    └── tests/gold/
        ├── book_card.example.json
        └── rubric_authoring.template.md
```

## 运行角色

```text
Codex：构建 Benchmark
        ↓
Harbor：harness / runner / verifier orchestration
        ↓
固定 Agent scaffold：首个 Pilot 为 Claude Code
        ↓
模型 backend
```

首个 Pilot 示例：

```bash
harbor run -p "tasks/<book-id>" -a claude-code -m "<anthropic-model>" -k 3
```

跨模型比较时，Harbor、Agent scaffold、系统提示词、工具、预算、采样和失败处理都必须冻结；只替换模型 backend。若不同模型使用不同 scaffold，结果只能解释为 Agent 系统比较。

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

该脚本验证 Schema、ID 唯一性、节点/关系/路径交叉引用、构成性案例规则和冻结状态。它不能代替人工确认内容是否忠于原书。

## 隐私与版权

正式书稿默认放在各 Task 的 `environment/source/`，该路径由 `.gitignore` 排除。仓库只保存说明文件、评分卡和可公开材料。公开或发布 Harbor Dataset 前需要单独检查授权。
