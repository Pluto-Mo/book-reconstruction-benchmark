# Book task template

这是单本书 Harbor task 的占位模板，不属于正式 dataset。

实例化时至少要完成：

1. 复制整个目录到项目根下的新任务目录；
2. 替换 `task.toml` 中的任务名和元数据；
3. 替换 `instruction.md` 的篇幅占位符；
4. 将私有书稿放入 `environment/source/`；
5. 依据 schema 完成 `tests/gold/book_card.json`；
6. 加入 oracle 参考输出并实现 verifier；
7. 通过全局资格考试与该书冒烟测试后，再用 `harbor add` 加入 dataset。
