# Breakthrough Advertising development task

这是一个可以由 Harbor 直接构建和执行的认知＋篇章开发 Task，不是正式排行榜 Task。

公开 instruction 已按 `natural` 压缩共读条件实例化；instruction 消融会另建隔离 Task，不在本任务内动态切换。

它已经接入：

- 6000–8000 字符硬约束；
- 60 条关系的 Evidence Locator 与 Relation Judge；
- 逐字引文验证；
- 16 条核心路径的确定性传播；
- 19 条固定面板 Authorial Edge 的严格 content gate、Locator 和双项 Judge；
- 结构提取、8 对局部推进、4 对全局顺序双反转、中心线、3 个案例与结尾探针；
- 数值 `reward.json` 与完整审计日志。

Harbor 兼容字段 `reward` 暂时仍等于 `cognitive_relation_coverage`；认知和篇章主指标全部单独写入 `reward.json`。跨维度排行榜公式尚未冻结。

开发期作者边只把 Book Card 的短证据摘要发送给 Judge，不发送长书摘；因此可用于协议接线和校准，不能冒充正式冻结的 Authorial Edge 分数。正式版本还需人工确认私有短摘录。

Judge 模型与 endpoint 已冻结在 Task；运行时只通过 Harbor secret 提供独立的 `QWEN_BENCHMARK_API_KEY`。书稿位于被 `.gitignore` 排除的 `environment/source/` 中。

~~~bash
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py --print-config
PYTHONPATH=scripts python3 scripts/run_pi_benchmark.py --write-config /tmp/pi-job.json
~~~

当前启动器固定一轮五模型 Pi job：GPT‑5.6 sol、Opus 5、Qwen 3.8 Max、K3、DS V4 Pro；Judge 固定 Qwen 3.8 Max 并开启 Qwen thinking。Agent 使用 Harbor 0.22 内置 Pi adapter 的最高档 `xhigh`；DeepSeek V4 将其映射为官方 `max`，其他 provider 使用各冻结记录可表达的最高思考模式。

三组比赛 provider 严格限定为 `openai-benchmark`、`qwen-benchmark`、`kimi-benchmark`，DeepSeek 严格使用官方 API。无密钥的 provider 配置随 Task 镜像交付；key 只通过 `OPENAI_BENCHMARK_API_KEY`、`QWEN_BENCHMARK_API_KEY`、`KIMI_BENCHMARK_API_KEY`、`DEEPSEEK_API_KEY` 四个 Harbor secret 名称绑定。启动器不读取个人 Pi `auth.json`、PAT、OAuth 或个人环境变量，也不回退到 `opencode-go`。

Harbor 托管运行使用 `credential_mode=direct` 与组织级 stored secrets；Task 必须先发布成冻结的 `org/name@ref`。Harbor 客户端不会自动上传本地 Task 路径，也不会上传任何本地 Pi 凭据文件。

Harbor 会原生处理 Task 解析、Agent 环境、artifact 传递、separate verifier、`tests/test.sh` 和 reward 回收。任务专用 verifier 实现两阶段语义协议、逐字引文校验、认知图传播、作者边 gate、固定抽样与位置反转；没有额外套 Rewardkit 运行层。

本地默认 Harbor 后端需要 `docker` 命令；托管后端需要 Harbor GitHub OAuth 和可用的 verifier secret。如果 Judge 模型或凭据缺失，verifier 会返回 `unscorable` 并且不写伪零分。
