# Evaluation Results

这里保存可复现且适合版本控制的 benchmark 测试结果，不保存私有书稿或凭据。

建议按一次正式评测一个目录组织：

```text
results/
└── <run-id>/
    ├── manifest.json            # dataset / task / verifier / runner / model 版本与运行参数
    ├── reward.jsonl             # 每个 task 的可审计奖励与诊断指标
    └── summary.md               # 跨书宏平均与简短结论
```

主榜结果必须来自固定篇幅、冻结任务契约和同一聚合规则。开放篇幅或实验性配置应明确标为消融结果，不与主榜混合。提交前请确认候选文章、日志与附件不含未经授权公开的书稿内容。
