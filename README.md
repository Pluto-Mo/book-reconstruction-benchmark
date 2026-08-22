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

## 项目结构

```text
book-reconstruction-benchmark/
├── dataset.toml                 # Harbor dataset manifest
├── metric.py                    # 跨书宏平均
├── docs/
│   ├── benchmark-v1.md          # 第一版问题与边界
│   └── harbor-mapping.md        # 本项目如何映射到 Harbor
├── schemas/
│   └── book-card.schema.json    # 单本书金标准卡草案
├── calibration/                 # 裁判资格考试与校准样本
├── configs/                     # 被测模型与 Harbor 的运行配置
├── tasks/                       # 审核通过的正式 benchmark 测试集
├── results/                     # 可复现、可公开的测试结果与汇总
└── templates/book-task/         # 一书一任务的 Harbor 模板
```

Harbor 中：一个 benchmark 对应一个 dataset，一本书对应一个 task。正式任务创建后可用：

```bash
harbor run -p "<task-path>" -a claude-code -m "<anthropic-model>"
```

本项目中的角色边界是：Codex 负责构建 benchmark；Harbor 是执行 harness；Claude Code 是首个由 Harbor 启动、读取书稿并产出文章的被测 agent。后续模型通过 API adapter 接入，但必须复用同一任务输入、输出契约和 verifier。

仓库名称为 `book-reconstruction-benchmark`。它同时承载 benchmark 定义、经审核的测试集、运行配置、校准材料及可复现的测试结果；模型接入方式本身不应分叉出另一套 benchmark。

详细设计从 [docs/benchmark-v1.md](docs/benchmark-v1.md) 开始阅读。

## 隐私与版权

正式书稿默认放在各 task 的 `environment/source/`，该路径已在根目录 `.gitignore` 中排除；仓库只保存说明文件、评分卡和可公开材料。公开或发布 Harbor dataset 前需要单独检查授权。
