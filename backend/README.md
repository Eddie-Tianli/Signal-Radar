# SignalRadar 后端

使用 FastAPI + SQLAlchemy + 本地 PostgreSQL。Topic API contract 保持不变；完整字段与接口见 [数据库设计](../docs/architecture/database-design.md) 和 [API 设计](../docs/api/api-design.md)。

## 统一 Item 模型

`app.collection.source.SourceAdapter.search(query)` 返回 `list[NormalizedItem]`，不直接持久化。使用 `ItemCreate(topic_id=topic_id, **normalized.model_dump())` 关联 Topic，再调用 `ItemService(session).create_item(data)`。通过 `list_topic_items(topic_id)` 查询。

普通创建遇到重复身份或不存在的 Topic 时抛出 IntegrityError 并回滚。`Item` 为读取 schema，与既有 Topic 命名一致。id 和 collected_at 由数据库生成；author、published_at、snippet 可为 null；published_at 输入必须包含时区。

source 最多 100 字符，external_id 最多 500 字符，必须稳定。`(source, external_id)` 全局唯一，包含跨 Topic 场景；目前每条内容只能属于一个 Topic。删除 Topic 会级联删除 Item 和 Digest。

YouTubeSource 为首个真实 Adapter；在后端配置 YOUTUBE_API_KEY 后使用 `POST /api/topics/{topic_id}/scan` 和 `GET /api/topics/{topic_id}/items`。扫描对身份冲突使用 ON CONFLICT DO NOTHING，整次事务提交。MockSource 仅供离线测试；FakeSource 仅在测试中使用，RSS 和 Web Search 尚未实现。

## 本地 PostgreSQL 配置

本机安装路径为 `D:\postgresql`，端口为 `9912`。在 PowerShell 以管理员数据库账户连接，交互输入密码：

```powershell
& 'D:\postgresql\bin\psql.exe' -h 127.0.0.1 -p 9912 -U postgres -d postgres
```

在 psql 中创建项目账户和数据库：

```sql
CREATE ROLE signalradar LOGIN;
\password signalradar
CREATE DATABASE signalradar OWNER signalradar;
\q
```

按提示设置项目密码。已有账户或数据库时不要重复创建或删除；使用拥有数据库或所需 schema 权限的账户，并相应调整 `.env`。

在 backend/ 下，仅当 `.env` 不存在时复制 `.env.example`。本地编辑 DB_PASSWORD，包含空格或 # 时加引号；不要将密码放入聊天、源码或 Git。进程环境变量优先于 `.env`。

## 安装、迁移与启动

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

开发时保持 SCHEDULER_ENABLED=false；启用自动任务时去掉 --reload 并使用单进程。Alembic 管理表结构，应用不会静默建表或回退到内存。每个请求独立 session，成功写入提交后关闭 session。Swagger：http://127.0.0.1:8000/docs。

## 验证持久化

1. 应用 migration 后，通过 Swagger 或前端创建 Topic。
2. 记录 ID，使用 `GET /api/topics/{id}` 查询。
3. Ctrl+C 停止 Uvicorn，再启动并查询同一 ID。
4. 确认字段仍存在，并在 http://localhost:3000/topics 验证编辑与删除。

旧内存版本进程退出后的数据无法恢复；当前版本使用 PostgreSQL 持久化。

## 自动化测试

```powershell
python -m pytest -q
```

默认测试使用隔离临时 SQLite 文件，覆盖 CRUD、migration、重新连接及回滚。SQLite 仅为测试工具，不是运行时回退方案；默认测试不使用配置的开发数据库，也不替代真实 PostgreSQL 验证。

可选本地 PostgreSQL 检查：

```powershell
$env:RUN_POSTGRES_TESTS = '1'
python -m pytest tests/test_items_postgresql.py -q
Remove-Item Env:\RUN_POSTGRES_TESTS
```

测试插入会回滚，但 sequence 可能前进。Windows 临时目录权限异常时使用新目录，不修改旧目录权限：

```powershell
python -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\signalradar-tests-$([guid]::NewGuid().ToString('N'))"
```

当前 head 为 0004。后续模型变更需生成并审阅 migration，再执行 upgrade head。不要在需要保留数据的数据库上降级：0001 删除 topics，0002 删除 items，0003 删除 AI 结果，0004 删除 Digest 历史。

本地启动、Ollama、Scheduler 和通知操作见 [本地开发指南](../docs/development/local-development)。
