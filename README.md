# LeanHarness：成本感知的 Agent Harness 优化

本仓库是 PE6203 项目 5 的小组代码库。项目研究的问题是：在**保持任务、模型和预算一致**的前提下，能否通过改进 AI agent 的“工具使用通道”，让它更稳定、更高效地完成 TUA-Bench 任务。

当前实现以 mini-SWE-agent 为基础，通过 Harbor 运行 TUA-Bench；Role 5（工具接口层）提供两份正式配置：

- **T1 / Result Normalizer**：将不同工具的杂乱返回结果整理成一致、短小、可读的格式；
- **T2 / Result Normalizer + Command Guard**：在 T1 基础上，额外对危险、重复或格式不正确的命令进行检查与提示。

有关“AI 助手发出命令 → 工具层处理 → 环境返回结果”的具体结构，请见 [工具接口说明](docs/tool-interface-map.md) 和 [Harbor 接入说明](docs/role5-harbor-integration.md)。

## 统一实验设置

| 项目 | 统一设置 |
| --- | --- |
| 基准测试 | TUA-Bench（固定 commit：`3497fd320abcafaf4797424192c891a593fd7964`） |
| 运行框架 | Harbor `0.6.3`、mini-SWE-agent `2.4.3`、Python `3.12.15` |
| 正式任务 | `configs/task_list_40.txt` 中的固定 40 题 |
| 正式配置 | 相同任务集、最多 30 步、单题最多 900 秒 |
| 便宜模型预算 | 单题最多 USD 0.06 |
| 团队总预算 | 目标 USD 35，绝对上限 USD 40 |

正式实验中，每个配置对每道题只运行一次；0 分和普通失败也必须保留。仅发生可确认的基础设施故障时可以重跑，并要在结果中记录原因。严禁提交 API Key，也不要运行 `harbor upload`。

## 快速开始

### 1. 前置条件

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop（已启动）
- OpenRouter API Key（仅真实模型实验需要）

在 macOS 上，如果终端找不到 Docker CLI：

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

### 2. 配置本地密钥

```bash
cp .env.example .env
```

然后在 `.env` 中填入本机自己的 `OPENROUTER_API_KEY`。`.env` 已被忽略，绝不能提交或发送给组员。

### 3. 无费用检查

```bash
/opt/homebrew/bin/python3.12 scripts/doctor.py
docker run --rm hello-world
/opt/homebrew/bin/uv run --group dev pytest
```

单元测试使用模拟执行器，不会访问 OpenRouter、Docker 任务容器或产生模型费用。

### 4. 初始化 TUA-Bench

```bash
cd vendor/TUA-Bench
/opt/homebrew/bin/uv sync
/opt/homebrew/bin/uv run setup-env
cd ../..
```

`setup-env` 会下载基准测试资源。首次正式实验前，先按 [实验指南](docs/role5-experiment-guide.md) 完成单题验证，确认 Harbor Exceptions 为 0。

## Role 5 配置与运行

| 配置 ID | 文件 | 作用 |
| --- | --- | --- |
| T1 | `configs/tool-interface-normalizer.yaml` | 仅启用 Result Normalizer |
| T2 | `configs/tool-interface-complete.yaml` | 启用 Result Normalizer 与 Command Guard |

批处理启动器位于 `scripts/run_role5_batch.py`。它会以固定任务顺序逐题运行、写入本地结果，并设置 Apple Silicon 所需的 `linux/amd64` Docker 平台。示例：

```bash
/opt/homebrew/bin/uv run python scripts/run_role5_batch.py \
  --configuration T1 \
  --task 000-count-nuclei \
  --task 003-rebuild-energy-model
```

按 `configs/task_list_40.txt` 的顺序重复添加 `--task <任务ID>`，即可组成顺序批次。运行前请先阅读并确认 [实验指南](docs/role5-experiment-guide.md) 中的模型、预算、输出目录和恢复规则。不要并发启动同一批任务，也不要用新的运行覆盖已有的正式结果。

## 结果、成本与分析

- 本地正式结果保存在 `results/role5/formal-results.csv`，原始运行目录在 `runs/role5-formal/`；二者均不提交到 GitHub。
- 每题至少记录：任务 ID、配置 ID、模型、reward、异常、运行时间、token 与实际费用。
- Harbor 可能将 OpenRouter 费用显示为 `0.0`；正式批次前后应查询 OpenRouter 的累计 usage，以差值核对真实成本。
- 分析规则与四项核心指标见 [Role 5 分析方案](docs/role5-analysis-protocol.md)。

## 目录说明

```text
adapters/       Harbor 与 mini-SWE-agent 的可复现接入代码
configs/        T1/T2 配置、固定任务清单与开发题清单
docs/           实验、接入、结果记录及分析文档
scripts/        环境检查、配置校验、运行与结果分析脚本
src/            LeanHarness 工具接口层实现
tests/          不产生模型费用的单元测试
templates/      结果记录表模板
contributions/  成员提交物的原样归档（非运行时依赖）
vendor/         第三方上游项目快照；请勿修改其 README
```

## 成员 2–5 的交付要求

成员可先用免费模型做单题开发，不需要等待共享 C0/C1。正式实验方案按其研究结构提交：

1. 若有两个可独立启用的组件 A、B：提交 A-only、B-only、A+B 三个配置，并分析组件贡献；
2. 若只有一个不可拆分的改动：只提交 A，并与共享 C0 比较；不要为了凑数量设计无研究意义的消融；
3. 若单项改动内仍有关键子组件：提交完整版及关闭该关键子组件的消融版。

每位成员还应交付改动与假设、配置 ID、精确运行命令、40 题完整结果、原始日志/轨迹，以及与 C0 和自身消融配置的对比分析。

## 归档 README 的处理原则

根目录的本文件是项目总入口。`contributions/liu-yalin/README.md` 和其 `developer_pack/README_zh.md` 是归档材料的目录说明，保留它们可以追溯提交来源和原始交付背景；它们不与根 README 重复，也不作为项目运行说明。`vendor/` 下的 README 属于上游依赖，保持原样。
