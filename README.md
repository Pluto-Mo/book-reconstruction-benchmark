# Book Reconstruction Benchmark

一个独立的 Harbor benchmark 项目，用来测量模型能否在高压缩整书重构中：

1. 保留一本书真正具有区分力的认知结构；
2. 避免把它压缩成正确但无信息量的常识；
3. 在可操作、可校准的范围内保留作者性组织。

当前状态：**V1 设计与脚手架阶段，尚未加入正式书目，也尚未形成可跑榜任务。**

## V1 基准问题

> 给定一本完整的非虚构作品和固定篇幅，模型能否重构该书特异的概念关系、限定条件与论证推进，而不是只生成一篇流畅的领域常识文章？

V1 暂定评分维度：

- 70%：书特异认知结构；
- 10%：抵抗常识化与空洞化；
- 10%：作者性组织；
- 10%：字数、格式与任务遵循。

权重是待校准的设计假设，不是既定结论。

## 核心设计

本项目借鉴 PaperBench 的不是代码复现流程，而是以下分层：

```text
共享的评分协议
        ↓
每本书独立的关系与认知原子树
        ↓
LLM Judge 只做证据优先的窄二元判断
        ↓
程序确定性汇总单书分数
        ↓
跨书宏平均
```

PaperBench 的 8,316 个叶子是 20 篇论文各自节点的总和。本项目同样只共享 Meta-Rubric 和 Judge 协议，不跨书复用具体内容叶子。

## 项目结构

```text
book-reconstruction-benchmark/
├── dataset.toml                 # Harbor dataset manifest
├── metric.py                    # 跨书宏平均
├── docs/
│   ├── benchmark-v1.md          # 第一版问题、样本与边界
│   ├── harbor-mapping.md        # 本项目如何映射到 Harbor
│   ├── paperbench-adaptation.md # 可迁移与不可照搬的设计
│   └── rubric-production.md     # Agent 辅助 Rebreak 和冻结协议
├── schemas/
│   ├── book-card.schema.json    # 单本书金标准卡
│   └── judge-result.schema.json # 单原子 Judge 结果
├── calibration/                 # 裁判资格考试与校准样本
├── configs/                     # 被测模型与 Harbor 的运行配置
├── tasks/                       # 审核通过的正式 benchmark 测试集
├── results/                     # 可复现、可公开的测试结果与汇总
└── templates/book-task/         # 一书一任务的 Harbor 模板
```

Harbor 中：一个 benchmark 对应一个 dataset，一本书对应一个 task。正式任务创建后可用：

```bash
harbor run -p "<task-path>" -a claude-code -m "<anthropic-model>" -k 3
```

本项目中的角色边界是：Codex 负责构建 benchmark；Harbor 是执行 harness；Claude Code 是首个由 Harbor 启动、读取书稿并产出文章的被测 agent。后续模型通过 API adapter 接入，但必须复用同一任务输入、输出契约和 verifier。

## 推荐阅读顺序

1. [V1 基准问题](docs/benchmark-v1.md)
2. [PaperBench 迁移原则](docs/paperbench-adaptation.md)
3. [Rubric 生产协议](docs/rubric-production.md)
4. [Harbor 映射](docs/harbor-mapping.md)

## 隐私与版权

正式书稿默认放在各 task 的 `environment/source/`，该路径已在根目录 `.gitignore` 中排除；仓库只保存说明文件、评分卡和可公开材料。公开或发布 Harbor dataset 前需要单独检查授权。
