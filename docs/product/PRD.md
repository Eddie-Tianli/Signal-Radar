# SignalRadar 产品需求（PRD）

## 阶段基线

本文保留早期“信息采集”规划的设计语义：当时主题（Topic）管理和 PostgreSQL 持久化已完成，内容采集是下一阶段。下文 Planned 描述历史设计范围，不代表当前代码或 migration 状态；当前功能清单以仓库 README 为准。

## 信息采集（Information Collection / Content Collection）— Planned

### 目标

由用户定义的 Topic 触发采集，将外部内容统一转换为内容条目（Item），并通过同一接口边界支持多个信息源（Source）。

### 预期流程

1. Topic 提供采集上下文和 query。
2. Collection Service 调用选定的 SourceAdapter。
3. Adapter 将平台返回的数据转换为统一 Item 字段。
4. 校验后关联 Topic，保存到 PostgreSQL。
5. 重复的 `(source, external_id)` 不创建新记录。

本阶段规划以用户手动触发为起点；自动任务（Scheduler）和后台任务基础设施不属于这份早期设计。具体 API 与界面交互在实现采集时明确。

### 计划验收标准

- 每个 Item 关联已有 Topic；不同来源输出相同内部结构。
- title 和 url 必填；author、snippet 和 published_at 可以缺失。
- collected_at 由系统记录，保留来源标识以识别重复内容。
- 后续 Source 复用同一持久化模型。

在这份历史规划中，YouTube、RSS、Web Search 仅为候选来源，AI 尚未开始；全文抓取、embedding、语义去重、事件聚类、简报（Digest）和登录均不属于该阶段。此处不将候选功能标记为已完成，也不撤销后续已实现能力。
