# CX R3-A 正式实验结果说明（可转发）

我们完成了 CX 的 R3-A detect-only 正式实验，共 40 题（含 smoke 的第 1 题）。配置为 Particle-1、mini-SWE-agent 2.4.3、Harbor 0.6.3、单并发、每题最多 30 步/900 秒；Failure Recovery 仅开启 detect，未开启 salvage。

结果：平均 reward 为 **0.6407**（总 reward 25.6269）；23 题满分、5 题部分得分、12 题 0 分；Harbor exception 为 0，未发生基础设施失败，也没有自动重跑。

实际 OpenRouter 费用合计 **USD 0.897653**，每题平均 USD 0.022441。注意 Harbor 汇总字段错误显示为 0；这里的费用改为从每题 trajectory 的 OpenRouter 回传 `upstream_inference_cost` 汇总。`054-prostate-label-obj` 和 `033-prostate-volume-est` 分别花费 USD 0.113809458 与 USD 0.111104222，略高于名义 USD 0.10 限额，说明这次运行中费用回传没有被限额机制有效约束。

详细逐题 reward、token、运行时长和真实费用见 `results/cx-r3-a/formal-results.csv`；方法、固定条件与数据来源见同目录 `README.md`。原始日志和 trajectory 保留在本地 `runs/cx-r3-a/`，未上传到 GitHub。
