# Hard constraints

程序检查输出文件、篇幅、格式、任务完成度和复制率。该目录不应使用 LLM 来完成可确定计算的项目。

篇幅使用仓库根目录 `scripts/count_submission_chars.py` 的 `nonwhitespace-codepoints-v1`：读取整个 UTF-8 提交文件，不做 normalization，计数固定 Unicode `White_Space` 集合以外的 code points。标题、标点、数字、组合附加符和 Markdown 标记均计入。计数日志必须保留 counter version、raw / whitespace / non-whitespace counts、上下限与 `within_bounds`。
