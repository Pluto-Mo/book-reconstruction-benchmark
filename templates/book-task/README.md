# Book task template

这是一个 Harbor 单任务脚手架，不属于正式 Dataset，也不代表 verifier 已经完成。

## Harbor 识别边界

当你把这个目录复制为：

```text
tasks/<book-id>/
```

并运行：

```bash
harbor run -p "tasks/<book-id>" -a oracle
```

Harbor 把 `tasks/<book-id>/` 视为 Task 根目录。根部必须保留：

```text
instruction.md
task.toml
environment/Dockerfile
solution/solve.sh
tests/test.sh
```

本模板还包含 Book Card、校准和 verifier 依赖；Harbor 允许 `tests/`、`solution/` 和 `environment/` 中存在额外文件。

## 为什么 tests/ 还有 Dockerfile

被测 Agent 使用 `environment/Dockerfile`，默认无网络。

模板将 verifier 配置为 `environment_mode = "separate"`，因此 Harbor 会从 `tests/` 构建独立 verifier 镜像。独立 verifier 模式不会在运行时自动上传 `tests/`，所以 `tests/Dockerfile` 必须把：

- `/tests/test.sh`；
- 隐藏 Book Card；
- Judge criteria；
- verifier 代码；

一起复制进镜像。

`task.toml` 中声明的 `/app/submission.md` artifact 会由 Harbor 传入 verifier 容器，并保持原路径。

## 实例化步骤

1. 复制整个目录到 `tasks/<book-id>/`；
2. 替换 `task.toml` 中的 Task 名、作者和元数据；
3. 替换 `instruction.md` 的篇幅占位符；
4. 将私有书稿放入 `environment/source/`；
5. 计算书稿 SHA-256，并建立稳定 Source Map；
6. 使用 `tests/gold/rubric_authoring.template.md` 完成核心问题、节点、关系、路径和案例分类；
7. 依据 `schemas/book-card.schema.json` 写入 `tests/gold/book_card.json`；
8. 运行 `scripts/validate_book_card.py`；
9. 按 `docs/rubric-production.md` 完成 Builder、Auditor、Red-Team 和人工审核；
10. 加入经审核 Oracle，并验证固定篇幅内满分可达；
11. 实现 Evidence Locator、Relation Adjudicator、Quote Validator 和 Graph Aggregator；
12. 让 `tests/test.sh` 产生纯数值的 `/logs/verifier/reward.json` 或单值 `reward.txt`；
13. 通过校准和该书冒烟测试；
14. 运行 Oracle：`harbor run -p "tasks/<book-id>" -a oracle`；
15. Oracle 达到预期分数后，用 `harbor add "tasks/<book-id>"` 写入 Dataset Manifest。

验证 Book Card：

```bash
uv run scripts/validate_book_card.py \
  --card tasks/<book-id>/tests/gold/book_card.json \
  --schema schemas/book-card.schema.json
```

## 当前故意失败的部分

当前 `tests/test.sh` 会写入：

```text
/logs/verifier/verifier-status.json
```

然后以非零状态退出，因为生产 verifier 尚未实现。它不会伪造一个合法的 0 分 `reward.json`。

正式 verifier 必须遵守：

- `reward.json` 的所有值都是数值；
- 字符串状态、版本、理由和引文放入其他日志；
- Judge API 错误不得伪装成被测模型零分；
- Judge 模型和凭据通过冻结运行配置或 `--ve` 注入。

不得用空 Book Card、未替换占位符、扁平观点列表或未经校准的整体 1–10 分 Judge 临时补齐。
