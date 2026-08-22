# Harbor 映射

本项目遵循 Harbor 当前的 `dataset → task → verifier/reward` 结构。

## 运行角色

```text
Codex（构建 benchmark）
          ↓
Harbor（harness / runner / verifier orchestration）
          ↓
Claude Code（被测 agent，在容器内完成书稿重构）
```

首个 pilot 的运行入口以 Claude Code 为准：

```bash
harbor run -p "tasks/<book-id>" -a claude-code -m "<anthropic-model>"
```

不要把 Codex 当前任务本身当作 Harbor 的被测 agent。

后续模型通过 API 接入时，新增的是 runner/adapter 配置，不是另一套 benchmark。跨模型比较必须冻结：

- 同一份书稿与公开任务说明；
- 同一输出文件与篇幅计算方式；
- 同一金标准卡、裁判版本和聚合权重；
- 同等的上下文、采样次数与失败处理规则。

因此任务层与模型接入层必须解耦：

```text
Harbor task + verifier（稳定）
              ↑
    ┌─────────┴──────────┐
Claude Code runner   API model adapters
```

| Harbor 概念 | 本项目中的含义 |
|---|---|
| Dataset | 整个 Book Reconstruction Benchmark |
| Task | 一次固定条件下对一本书进行高压缩重构 |
| `instruction.md` | 对被测模型公开的写作任务和篇幅约束 |
| `environment/source/` | 该任务提供的书稿及允许公开给模型的材料 |
| `solution/` | 经审核的 oracle 输出；不是唯一正确措辞 |
| `tests/gold/` | 隐藏的书特异关系卡、锚点和评分配置 |
| Verifier | 硬约束检查、证据提取、二元语义判断与复核 |
| `reward.json` | 各维度分数、主分和可审计诊断指标 |
| `metric.py` | 先对单书归一化，再跨书进行宏平均 |

## 单本书任务目录

```text
<book-task>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   └── source/                 # 私有书稿，默认不进 git
├── solution/
│   ├── solve.sh
│   └── reference_submission.md
└── tests/
    ├── test.sh
    ├── reward.toml
    ├── gold/book_card.json
    ├── hard_constraints/
    ├── cognitive_structure/
    ├── genericity_resistance/
    └── authorial_organization/
```

## 预期 reward 输出

```json
{
  "reward": 0.64,
  "cognitive_structure": 0.61,
  "genericity_resistance": 0.50,
  "authorial_organization": 0.70,
  "hard_constraints": 1.00,
  "judge_disagreement_rate": 0.08
}
```

`reward` 由程序按冻结权重计算。`judge_disagreement_rate` 是诊断指标，不应被混入质量分。

## 当前初始化边界

模板遵循 Harbor 的任务目录约定，但还不是正式可跑任务：尚未选择书、写入书稿、冻结金标准卡、提供 oracle 输出或接通生产 verifier。首次可运行里程碑应由一本文本合法、结构清楚的 pilot 书完成。
