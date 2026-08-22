# Book task template

这是一个 Harbor 单任务脚手架，不属于正式 Dataset，也不代表 verifier 已经完成。

## Harbor 识别边界

复制为：

```text
tasks/<book-id>/
```

Harbor 将该目录视为 Task 根。根部必须保留：

```text
instruction.md
task.toml
environment/Dockerfile
solution/solve.sh
tests/test.sh
```

本模板还包含 Book Card、Discourse Card、校准和 verifier 依赖；Harbor 允许在 `tests/`、`solution/` 和 `environment/` 中放置额外文件。

## 为什么 tests/ 还有 Dockerfile

被测 Agent 使用 `environment/Dockerfile`，默认无网络。

模板将 verifier 配置为独立环境，因此 `tests/Dockerfile` 必须把：

- `/tests/test.sh`；
- 隐藏 Book Card；
- 隐藏 Discourse Card；
- Judge criteria；
- verifier 代码；

一起复制进镜像。`/app/submission.md` artifact 由 Harbor 传入 verifier，并保持原路径。

## 实例化步骤

1. 复制目录到 `tasks/<book-id>/`；
2. 替换 `task.toml` 中的 Task 名、作者和元数据；
3. 将 `instruction.md` 写成自然的真实编辑任务，并冻结篇幅；
4. 将私有书稿放入 `environment/source/`；
5. 计算书稿 SHA-256，并建立稳定 Source Map；
6. 使用 `tests/gold/rubric_authoring.template.md` 完成核心问题、节点、关系、路径和案例分类；
7. 依据 `schemas/book-card.schema.json` 写入 `tests/gold/book_card.json`；
8. 运行 `scripts/validate_book_card.py`；
9. 使用 `tests/gold/discourse_authoring.template.md` 从审核后的 Source Anchors 建立有意义的作者关系边池；不得从全书所有段落对中任意随机抽样；
10. 冻结分层面板、编辑探针、扰动和权重，写入 `tests/gold/discourse_card.json`；
11. 运行 `scripts/validate_discourse_card.py`；
12. 完成 Builder、Auditor、Red-Team 和人工审核；
13. 加入经审核 Oracle，并验证固定篇幅内认知与篇章高分可达；
14. 实现 Cognitive Structure Pipeline；
15. 实现 Authorial Edge Recovery 和 Editorial Coherence Pipeline；
16. 让 `tests/test.sh` 产生纯数值的 `/logs/verifier/reward.json` 或单值 `reward.txt`；
17. 通过认知校准和篇章扰动校准；
18. 运行 Oracle：`harbor run -p "tasks/<book-id>" -a oracle`；
19. Oracle 达到预期后，用 `harbor add "tasks/<book-id>"` 写入 Dataset Manifest。

验证：

```bash
uv run scripts/validate_book_card.py \
  --card tasks/<book-id>/tests/gold/book_card.json \
  --schema schemas/book-card.schema.json

uv run scripts/validate_discourse_card.py \
  --card tasks/<book-id>/tests/gold/discourse_card.json \
  --schema schemas/discourse-card.schema.json \
  --book-card tasks/<book-id>/tests/gold/book_card.json
```

## 当前故意失败的部分

当前 `tests/test.sh` 会先检查两张正式 Card，然后写入 `verifier-status.json` 并以非零状态退出，因为生产 verifier 尚未实现。它不会伪造一个合法的 0 分。

正式 verifier 必须遵守：

- `reward.json` 的所有值都是数值；
- 字符串状态、版本、引文、边面板和 Judge 理由放入其他日志；
- Judge API 错误不得伪装成被测模型零分；
- 所有模型使用同一冻结 Panel 和 Probe 算法；
- Pairwise 判断执行 A/B 位置反转；
- 最终总分由程序计算，Judge 不直接发明。

不得用空 Card、未替换占位符、任意段落对、整体 1–10 分“作者感”或整体“流畅度”临时补齐。
