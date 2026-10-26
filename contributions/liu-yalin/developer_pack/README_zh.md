# PE6203 项目5：成员2–5开发包

## 固定环境
- TUA-Bench commit：3497fd320abcafaf4797424192c891a593fd7964
- Harbor：0.6.3；mini-swe-agent：2.4.3；Python：3.12.15
- 基础配置：settings/mini_base.yaml
- 固定任务：settings/task_list_40.txt

## 统一设置
- 所有正式配置使用相同40题、30步、单题最多900秒。
- 便宜模型单题上限0.06美元；C1/CX单题上限0.10美元。
- 小组目标35美元，绝对上限40美元。
- 每个正式配置只运行一次；普通失败和0分不得删除。
- 只有基础设施故障可以重跑，并记录原因。
- 禁止共享或打包API密钥；不要运行harbor upload。

## 成员2–5任务
无需等待C0/C1，可立即用免费模型做单题开发。每人提交：
1. 一个主方案配置；
2. 一个关键消融配置；
3. 改动内容和假设；
4. 完整配置及精确命令；
5. 固定40题结果；
6. 原始结果、日志和轨迹。

开始40题前，必须先成功运行1题且Harbor Exceptions为0。

## 依赖修复
Harbor安装mini-swe-agent时缺少LiteLLM proxy依赖，可能出现No module named mcp。先定位并备份适配器，再把安装命令中的：
uv tool install mini-swe-agent{version_spec} &&
替换为：
uv tool install --with 'litellm[proxy]' mini-swe-agent{version_spec} &&

这是统一环境兼容修复，不属于harness改进，所有成员必须一致应用并在报告披露。

## 结果与成本
每题保留task ID、配置ID、模型、reward、exception、runtime、input/output tokens和费用。
Harbor可能把OpenRouter费用显示为0.0；正式批次前后查询OpenRouter累计usage，以差值作为真实成本。

## 示例
examples/c0_single_task为C0单题试跑：Exceptions=0、Reward=0、实际消费约0.01626美元。它仅证明链路可运行，不是正式C0结果。
