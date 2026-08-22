# Judge Calibration

这里保存裁判资格考试，不保存正式模型输出。

建议结构：

```text
calibration/
├── global/                     # 跨书共用的裁判能力测试
│   ├── cases.jsonl
│   └── expected.jsonl
└── per-book/
    └── <book-id>/              # 每书最小冒烟测试
        ├── cases.jsonl
        └── expected.jsonl
```

每个变体必须记录：原始文本、只改变了什么、哪些原子标签应变化、哪些维度不应变化。由 AI 生成的扰动仍需 benchmark 作者确认它只改变目标变量。
