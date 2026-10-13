# 本地开发指南

## Windows 本地使用

启动顺序：**PostgreSQL → Ollama → SignalRadar**。PostgreSQL 可能已作为 Windows 服务运行；按本机已有方式启动即可。Ollama 可从桌面应用或 `ollama serve` 启动，已运行时不要重复启动。使用 `ollama list` 确认模型。

首次准备：创建 backend/.venv，安装 requirements-dev.txt，配置 backend/.env，在 backend/ 执行 `python -m alembic upgrade head`，在 frontend/ 执行 `npm install`。Node.js/npm 需在 PATH 中。

在仓库根目录运行：

```powershell
.\start-signalradar.ps1 -CheckOnly
.\start-signalradar.ps1
```

脚本检查虚拟环境、.env、node_modules、Node/npm、数据库连通性、migration 0004、8000/3000 端口和本地 Ollama /api/tags。随后构建 Next.js，运行生产前端及单进程后端。只有构建与当前代码一致时才使用 -SkipBuild。脚本不会自动安装依赖、迁移数据库、启动 PostgreSQL / Ollama 或修改 Windows 配置。若执行策略阻止脚本，按本机允许的方式处理；脚本不会自行修改执行策略。

Ollama 离线会记录 `Ollama unavailable - AI analysis will fail until Ollama is started.`，应用仍能启动。数据库或必需文件缺失则阻止启动并提示处理方式。访问 http://localhost:3000 和 http://127.0.0.1:8000/api/status。后者保留 name/version/status，增加 database、ollama、scheduler、notifications；available 只表示 Ollama API 响应，不保证 OLLAMA_MODEL 已配置和安装。

保持终端打开，Ctrl+C 等待当前请求完成或超时，再关闭自身启动的前端进程树。不要在写入时强制关闭。日志位于 logs/signalradar.log，每 2 MB 轮转并保留 3 份备份，已被 Git 忽略。Windows 休眠会暂停运行；不提供开机、登录自启或系统服务安装。

## PostgreSQL 与后端

账户和数据库配置见 [后端说明](../../backend/README.md)。开发命令（Scheduler 关闭时）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

在另一个终端从 frontend/ 执行 `npm run dev`。主题页面：http://localhost:3000/topics。

## MockSource 离线采集（仅开发和测试）

设置 backend/.env 中的 `USE_MOCK_SOURCE=true` 并重启，也可在启动后端的 PowerShell 中设置 `$env:USE_MOCK_SOURCE = 'true'`。进程环境变量优先，不需要 YouTube Key。未设置或 false 时使用 YouTube；切换需修改实际生效配置并重启。

1. 启动本地 PostgreSQL、后端和前端。
2. 创建名为 Christopher Nolan 的 Topic，干净测试可使用新名称。
3. 点击“扫描”，预期 source=mock、fetched=3、created=3、duplicates=0。
4. 页面展示 3 条模拟内容，source 为 mock。
5. 再次扫描，预期 fetched=3、created=0、duplicates=3。
6. 刷新页面或重启后端，内容仍存在。

ID 由标准化 query 和样本索引生成。全局 `(source, external_id)` 约束也会对相同 query 的不同 Topic 去重，因此新 Topic 首次扫描可能已经是重复项。发布日期固定，链接指向 localhost 占位页面，不是真实文章。

MockSource 不创建 HTTP 客户端；前端只请求本地后端，后端连接本地 PostgreSQL。可在浏览器 DevTools 检查 Scan / Items 请求目标为 127.0.0.1:8000，外链不会自动加载。Mock 测试拒绝非回环 socket，并在 YouTubeSource.search 被调用时失败。

## 本地 Ollama 分析

1. 启动 Ollama；尚未运行时可执行 `ollama serve`。
2. 使用 `ollama list` 获取已安装模型的完整名称；用 `Invoke-RestMethod http://localhost:11434/api/tags` 检查服务。
3. 设置 OLLAMA_BASE_URL=http://localhost:11434、OLLAMA_MODEL 为实际模型名称，USE_MOCK_SOURCE=true。不会自动下载模型；修改后重启。
4. 激活后端虚拟环境，执行 `python -m alembic upgrade head`、`python -m alembic current`（0004 head）。
5. 创建 Topic 并扫描，在内容卡片点击“分析”，或“分析未处理内容”。先少量测试，本地模型可能较慢，单次后端调用超时为 120 秒。
6. 查看相关性、评分、分类、AI 摘要和分析时间；刷新后仍应存在。

Swagger 也可使用 `POST /api/items/{item_id}/analyze` 或 `POST /api/topics/{id}/analyze?limit=1`。数据库检查语句：

```sql
SELECT id, ai_relevant, ai_relevance_score, ai_category, ai_summary, ai_analyzed_at FROM items;
```

MockSource 只模拟内容，不模拟 AI；正常浏览器流程仍依赖 Ollama。自动测试使用 FakeAI 和 MockTransport，不真实推理。结构化输出参考：https://docs.ollama.com/capabilities/structured-outputs。

## Ollama 调试日志

完整 Trace 默认关闭，与普通 DEBUG 日志级别独立。需要定位 Item Analyze 或 Digest 失败时，在 `backend/.env` 设置：

```ini
OLLAMA_TRACE_ENABLED=true
```

重启后端后，手动执行一次“分析”或“生成简报”。进程环境变量优先于 `.env`，如已在 PowerShell 设置该变量，也需要同步修改。无需启动 Scheduler 或修改模型。日志自动追加到：

```text
backend/logs/ollama_trace.jsonl
D:\Projects_ltl\Signal-Radar\backend\logs\ollama_trace.jsonl
```

目录自动创建且被 Git 忽略。每行是一条 UTF-8 JSON 事件，包含 UTC 时间戳、stage（item_analyze / digest）、attempt、request_id、call_id 和 parent_request_id。每次 HTTP 尝试有独立 request_id；一次业务调用及其重试共享 call_id，第二次的 parent_request_id 指向第一次。Digest 事件还包含本次 item_count。

| event | 用途 |
| --- | --- |
| request | 最终构建的 HTTP 请求正文、payload、messages、system_message、user_message、format、options、temperature、stream、model 和 endpoint；prompt 是完整 messages 的副本，不是模板 |
| response | 在 JSON 解析前保存原始响应正文 raw_response、HTTP status_code 和 elapsed_ms |
| response_details | 可解析时记录完整 response_json、原始 message.content、返回 model 和 token/耗时统计 |
| http_error | 连接或超时等请求异常，包含异常类型和 http_request 阶段 |
| server_error | Ollama 返回非成功 HTTP status code；原始响应已先保存 |
| response_structure_error | 响应不是合法 JSON，或缺少 message.content 等结构异常 |
| empty_content | message.content 为 null、空字符串或仅空白 |
| json_parse_error / parse | 内容 JSON 解析失败或成功，以及 direct、code_fence、object_extraction 路径；首次直接解析失败后仍可能容错成功 |
| validation_error | Pydantic 字段校验错误，details 包含 loc、type、msg，不附带重复的输入值 |
| business_validation_error | 语言、Topic 关键词或任务漂移等业务检查失败 |
| retry / retry_failed | 重试原因与下一 attempt；第二次仍失败时记录最终失败 |
| complete | 当前尝试成功通过解析和校验 |

在仓库根目录用 PowerShell 查看最新 Digest 调用及所有重试：

```powershell
$tracePath = '.\backend\logs\ollama_trace.jsonl'
$events = Get-Content -LiteralPath $tracePath -Encoding utf8 | ForEach-Object { $_ | ConvertFrom-Json }
$latest = $events | Where-Object { $_.stage -eq 'digest' -and $_.event -eq 'request' } | Select-Object -Last 1
$events | Where-Object { $_.call_id -eq $latest.call_id } | Select-Object timestamp, request_id, attempt, event
$events | Where-Object { $_.call_id -eq $latest.call_id } | ConvertTo-Json -Depth 100
```

只查看某一次 HTTP 尝试的实际发送内容和原始返回：

```powershell
$requestId = $latest.request_id
$attemptEvents = $events | Where-Object { $_.request_id -eq $requestId }
($attemptEvents | Where-Object { $_.event -eq 'request' }).payload | ConvertTo-Json -Depth 100
($attemptEvents | Where-Object { $_.event -eq 'response' }).raw_response
$attemptEvents | Where-Object { $_.event -match 'error|failed|retry' } | ConvertTo-Json -Depth 100
```

不要只看最终通用错误：先确认 response 的 HTTP 状态，再查看具体错误事件。schema 错误可由 details 定位到 summary 等字段；业务检查失败与 JSON 格式失败会分开记录。Trace 不增加推理调用，原有最多一次重试、Prompt、Schema 和筛选规则不变。

关闭时设置 `OLLAMA_TRACE_ENABLED=false` 并重启。关闭后不记录 Prompt、Item 正文或模型生成内容，即使普通日志处于 DEBUG 级别；已有日志文件不会自动删除。Trace 开启时保留完整正文，不做截断，但会对已知环境凭据、认证值及常见凭据格式脱敏，不记录 HTTP headers 或环境变量列表。脱敏只影响日志副本，不修改实际请求或响应。

日志仅写本机，不上传任何外部服务；写入失败只产生安全警告，不使 Analyze 或 Digest 失败。目前采用追加写入，没有轮转。**日志仍包含私人 Topic、Item 摘要、原始输入和模型回复，不能直接上传公开仓库或公开分享；诊断结束后及时关闭。**

## Digest 与自动任务

1. 设置 USE_MOCK_SOURCE=true、SCHEDULER_ENABLED=false，启动已配置模型的 Ollama。
2. 执行 `python -m alembic upgrade head`、`python -m alembic current`、`python -m alembic check`，确认 0004 head。
3. 启动前后端，创建 Topic，点击“扫描”和“分析”。
4. 至少一条内容需被判断为相关，否则“生成简报”返回 409；全部不相关也可能是正常模型判断。
5. 点击“生成简报”，检查 AI 标记、标题、引用数、时间和摘要；“查看历史简报”读取保存的快照。
6. 重启后端并刷新历史，确认持久化。对应 API 为 `POST /api/topics/{id}/digest` 和 `GET /api/topics/{id}/digests`。
7. 验证自动任务时创建新名称的启用 Topic，停止后端，设置 SCHEDULER_ENABLED=true、SCAN_INTERVAL_MINUTES=1，再以单进程 `uvicorn app.main:app` 启动，不使用 --reload 或多个 worker。
8. 等待一分钟加推理时间，查看日志中的 Topic ID、扫描与分析数量、Digest created/skipped，再刷新内容和简报历史。
9. 下一轮无变化的 Mock 扫描不会插入重复内容、重新分析或重复生成简报。只处理启用的 Topic，每轮每 Topic 最多处理 20 条待分析内容，包括此前遗留内容。

安全关闭：Ctrl+C，等待当前请求完成或超时；停止信号之后不启动下一条内容或 Topic。将 SCHEDULER_ENABLED=false 后重启即可保留手动功能。进程环境变量优先于 .env，注意同步清除或修改已有设置。间隔范围 0.1–10080 分钟，默认 60；首次等待完整间隔，下一轮从上一轮完成后开始等待。

不要同时运行多个后端或让手动工作流与 Scheduler 竞争。锁仅在单进程内生效，没有分布式锁。分析成功但 Digest 失败时，可手动生成恢复；没有持久化重试队列。

## Windows 通知验证

1. 启动 PostgreSQL、Ollama，设置 USE_MOCK_SOURCE=true 和正确 OLLAMA_MODEL。
2. 设置 SCHEDULER_ENABLED=true、SCAN_INTERVAL_MINUTES=1、NOTIFICATIONS_ENABLED=true。
3. 运行启动脚本，创建名称唯一且启用的 Topic，等待首轮及推理时间，不同时手动分析。
4. 新相关内容产生且 Digest 保存后，应发送包含 Topic 与相关数量的 SignalRadar 通知；Windows 归到 Windows PowerShell。全部不相关时不通知。
5. 检查历史和日志：Scan completed、Analysis completed、Digest created、Notification sent、Topic job completed。下一轮无变化时跳过 Digest 和通知；模型或简报失败仅记日志。
6. 关闭 NOTIFICATIONS_ENABLED 并重启，用新 Topic 验证简报正常保存但不通知。专注助手或系统设置可能抑制横幅，请检查通知中心。
7. Ctrl+C 后设置 SCHEDULER_ENABLED=false 并重启，安全关闭自动任务。

仅自动任务成功的新简报通知，手动生成不通知。发送失败记录 Notification failed，不影响业务完成。不弹通知的 payload 检查：

```powershell
'{"topic":"Local test","count":3}' | powershell -NoProfile -NonInteractive -File backend/app/notifications/toast.ps1 -ValidateOnly
```

自动测试强制关闭真实通知，使用 FakeNotification。

## YouTube API Key 与真实手动扫描

纯本地测试使用 MockSource，无需配置 YouTube。

1. 在 Google Cloud 创建或选择项目，启用 YouTube Data API v3。
2. 创建 Key，将 API 访问限制为 YouTube Data API v3，选择适用于服务端的应用限制；仅浏览器 referrer 限制不适合后端调用。
3. 本地编辑 backend/.env，填写 YOUTUBE_API_KEY，或设置后端进程环境变量。不要放入前端变量、源码、截图或 Git；模板仅保留空占位。
4. 设置 USE_MOCK_SOURCE=false 并重启。公开视频搜索不需要 OAuth。
5. 在 http://127.0.0.1:8000/docs 创建 Topic，记录 ID，执行无 body 的 `POST /api/topics/{topic_id}/scan`。
6. 检查 source=youtube、fetched=created+duplicates，最多 15 条；通过 `GET /api/topics/{topic_id}/items` 查看链接、标题、作者和日期。
7. 重复扫描会再次消耗配额，实时结果可能改变，不保证 created=0。重启后端后检查内容持久化。

503 提及 YOUTUBE_API_KEY 表示配置缺失；502 检查 API 启用、Key 限制、配额和网络；504 为超时。不要共享原始上游错误日志或将 Key 放入请求 URL。

官方参考：
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/youtube/v3/docs/search/list

## 自动化测试

### Windows 临时目录约定

2026-10-08 已复现默认 `pytest-of-80538` 权限问题：`tmp_path` fixture 在 pytest 的 `find_prefixed` / `os.scandir` 枚举 `C:\Users\80538\AppData\Local\Temp\pytest-of-80538` 时出现 `PermissionError: [WinError 5]`。错误发生在测试 setup 阶段，业务断言和数据库操作尚未执行；并非 Item、AI 或 Digest 逻辑失败。

以后运行后端测试必须：

1. 使用项目外部独立根目录 `D:\pytest-temp`。
2. 每次 pytest 调用生成新的 GUID 子目录，不复用上一轮路径。
3. 使用 `--basetemp $testTempPath`；pytest 创建该新子目录。不要将根目录本身作为 basetemp，也不要指定包含需要保留文件的现有目录，因为 pytest 会清理指定的 basetemp。
4. 同时使用 `-p no:cacheprovider`，避免写入已有权限异常的 `.pytest_cache`。
5. 因 PermissionError 失败时先确认路径和 setup 堆栈，不修改业务逻辑、不删除测试、不降低覆盖率，也不修改系统目录 ACL。

以下完整、单文件或单测试命令都遵循相同约定。每次重新运行整段命令，以获取新 GUID；针对性测试只在 pytest 后补充测试路径或 node ID，其余参数不变。

在 backend/ 中执行，不消耗真实 API 配额，也不调用 Ollama：

```powershell
$testTempRoot = 'D:\pytest-temp'
New-Item -ItemType Directory -Path $testTempRoot -Force | Out-Null
$testTempPath = Join-Path $testTempRoot ([guid]::NewGuid().ToString('N'))
python -m pytest -q -p no:cacheprovider --basetemp $testTempPath
```

使用 httpx.MockTransport 覆盖成功、重复、失败和超时响应，数据库默认采用临时 SQLite。Scheduler 测试直接调用 run_cycle，不启动永久线程，即使本地 .env 启用也强制关闭后台启动。

可选本地 PostgreSQL 检查（测试行回滚，sequence 可能前进）：

```powershell
$env:RUN_POSTGRES_TESTS = '1'
$testTempRoot = 'D:\pytest-temp'
New-Item -ItemType Directory -Path $testTempRoot -Force | Out-Null
$testTempPath = Join-Path $testTempRoot ([guid]::NewGuid().ToString('N'))
python -m pytest -q -p no:cacheprovider --basetemp $testTempPath
Remove-Item Env:\RUN_POSTGRES_TESTS
```

前端验证：

```powershell
cd frontend
npm run lint
npm run build
```

## v0.1.1 一键更新与人工验收

推荐在“我的主题”点击“一键更新”，自动采集、去重、逐条分析并按需生成简报。当前阶段、成功数量、失败阶段和剩余待处理数量会实时显示。高级操作仍有“仅扫描 / 仅分析未处理内容 / 仅生成简报”。点击“查看内容”可筛选全部、待分析、相关和不相关；点击简报“展开阅读”进入阅读页并切换历史。

每次最多分析 20 条待处理内容；Digest 最多使用 10 条已分析、相关且摘要非空的 Item。按 relevance_score DESC NULLS LAST、发布时间或采集时间 DESC、id DESC 稳定排序。不相关内容保留，最终 Digest 不读取原始 snippet。输出为中文纯文本，不伪造引用关系。

深度推理模型的 thinking 也消耗 num_predict。旧 Trace 中 2048 预算耗尽，出现 HTTP 200 但 content 为空；现 Digest 第一次 4096、重试 8192，每次 180 秒。空回复和超时有独立提示，完整原因查看 Trace。不要将 thinking 当作最终正文。单条分析仍为 120 秒。

页面刷新或离开后不会恢复处理中进度，当前推理可能仍在完成。刷新结果再决定重试，409 表示该主题仍忙。锁只在单进程内生效，使用单个 Uvicorn，启用 Scheduler 时不要加 --reload 或多个 worker。没有后台任务系统，当前终端仍需保持运行。

前端 API 测试无需新框架，使用 Node 内置 test runner 和已有 TypeScript：

```powershell
cd frontend
npm run test:api
npm run lint
npm run build
```

完整本机人工验收：

1. 启动 PostgreSQL 和 Ollama，确认端口 9912、11434 可用；配置真实本地凭据和已安装 OLLAMA_MODEL。
2. 设置 USE_MOCK_SOURCE=true、SCHEDULER_ENABLED=false、NOTIFICATIONS_ENABLED=false。
3. 使用根目录 start-signalradar.ps1，或分别运行后端与 npm run dev。
4. 打开总览，检查计数及系统状态；创建新 Topic，点击一键更新。
5. 观察采集 → 分析 → 简报，检查进度、内容、AI 标记和简报历史。
6. 再次更新，确认重复数据跳过、已分析内容不重复处理、无变化不生成新简报。
7. 重启后端并刷新，确认内容、分析和简报仍存在。
8. 在普通桌面窗口和约 760px 窄窗口检查导航、按钮、长标题、筛选、简报阅读及键盘焦点。
9. 停止 Ollama（确认没有其他依赖它的任务）后验证扫描和阅读仍可用、分析给出明确错误。也可仅将测试进程 OLLAMA_BASE_URL 指向未使用的本机端口，避免停止全局服务。
10. 最后单独启用 Scheduler，验证其与手动操作同 Topic 不重叠；结束后可关闭配置。

本轮实际验收结果及尚未完成的项目见 [v0.1.1 验收记录](v0.1.1-acceptance.md)。不要将隔离 SQLite 验收描述为 PostgreSQL 验收，也不要将静态 HTTP 检查描述为浏览器视觉验收。
