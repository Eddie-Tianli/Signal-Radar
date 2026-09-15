# ADR-002：统一内容模型（Unified Content Model）

状态：Proposed（信息采集阶段设计，保留原始决策状态）

## 背景（Context）

SignalRadar 计划围绕用户定义的 Topic 接入多个来源，例如 YouTube、RSS 和 Web Search。各平台的响应格式、标识符和元数据不同。本文记录当时的设计选择，不是集成完成情况或当前 migration 清单。

## 决策（Decision）

采用统一 Item 模型，包含 Topic 关联、来源标识、title、url、可选 author / published_at / snippet，以及系统记录的 collected_at。SourceAdapter 在持久化之前完成标准化；计划对 `(source, external_id)` 建立唯一约束，按来源身份去重。

该阶段不分别创建 YouTubeItem、RSSItem、WebItem 表，不提前定义 AI、embedding、event 或生成摘要字段。

## 备选方案（Alternatives Considered）

- **每个平台一张表**：便于保留特有字段，但公共字段、migration、查询及下游逻辑重复。
- **仅保存原始 JSON**：初期写入简单，但使用方依赖平台格式，统一校验和查询更困难。
- **统一 Item**：提供稳定内部约定，通过 nullable 字段处理缺失元数据；因此选用此方案。

## 影响（Consequences）

- 采集、持久化和展示共用一致的数据约定。
- Adapter 负责格式转换，并建立稳定的 source 和 external_id。
- 初版不保存所有平台元数据；有明确需求时再增加字段。
- 全局来源标识唯一约束可以阻止身份重复，但不提供语义去重或跨 Topic 归属。
- ADR 本身不实现信息源、网络请求、migration、Scheduler 或 AI 功能。
