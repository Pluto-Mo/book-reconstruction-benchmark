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

每个变体必须记录：

- 原始文本或基准文本 ID；
- 只改变了什么；
- 哪些原子标签应变化；
- 哪些维度不应变化；
- 人工确认人；
- 使用的 Book Card、Judge Prompt 和模型版本。

由 AI 生成的扰动仍需 Benchmark 作者确认它只改变目标变量。

最低覆盖类型：

1. 语义保持改写；
2. 只保留最终结论；
3. 常识替换；
4. 术语堆砌；
5. 删除限定；
6. 关系反转；
7. 漂亮空话。

开发书可用于反复修改 Judge；保留书的冒烟测试和预期标签必须在正式模型输出产生前冻结。

不要只报告一个总体准确率。至少分别统计：

- false positive；
- false negative；
- 关系反转识别；
- 语义保持改写一致性；
- 重复 Judge 或多 Judge 分歧率。

关键关系反转样本仍出现 false positive 时，不得冻结该书任务。
