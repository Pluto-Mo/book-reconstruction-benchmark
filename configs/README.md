# Run configurations

这里保存 Harbor 运行配置。首个 pilot 使用 Harbor 原生 Pi scaffold；配置可以改变 model、并发与凭据注入方式，但不得按模型改变单书 task 的公开说明、输入材料、工具、篇幅、输出契约或 verifier。

cognitive-provider.example.json 展示所有语义 Locator / Judge 共用的厂商无关配置。它不是可运行的正式配置：adapter 路径和完整模型版本必须在校准后替换并冻结，凭据只通过 verifier 环境变量注入。

`tasks/breakthrough-advertising-dev/tests/cognitive-provider.json` 是已接入 Harbor verifier 的开发配置。运行时 `harbor_cognitive_verifier.py` 使用 `BENCHMARK_JUDGE_MODEL` 填入完整 LiteLLM 模型标识；`BENCHMARK_JUDGE_API_KEY`、`BENCHMARK_JUDGE_BASE_URL` 与 thinking 开关只进入独立 verifier。两次协议尝试、语义判定、引文校验、图聚合、固定抽样和位置反转都由任务运行层控制。

`pi-five-models.json` 冻结本轮五模型次序、唯一允许路由、Pi 版本、逐路线 thinking 控制和 Qwen Judge。非敏感 provider 定义位于开发 Task 的 `environment/pi/models.json`，其中 `apiKey` 只能是本地运行时凭据引用，不能出现实际值。GPT‑5.6 sol 与 Opus 5 只使用 `openai-benchmark`；Qwen 与 K3 分别只使用 `qwen-benchmark`、`kimi-benchmark`；DS V4 Pro 只使用 DeepSeek 官方 API。

Pi 的统一 thinking selector 只作为转换层：GPT/Opus/K3 当前由 provider 管理，Qwen 转成 `enable_thinking=true` 与 `reasoning_effort=high`，DeepSeek 转成 `reasoning_effort=max`。启动器只在本机 Harbor 运行，不读取个人 Pi `auth.json`、PAT、OAuth 或当前 shell 中的个人 provider key，也不回退到 `opencode-go`。`--run` 只接受仓库外、`0600` 的显式 secrets 文件。
