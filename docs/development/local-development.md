# 本地开发指南

## Windows 本地使用

启动顺序：**PostgreSQL → Ollama → SignalRadar**。PostgreSQL 可能已作为 Windows 服务运行；按本机已有方式启动即可。Ollama 可从桌面应用或 `ollama serve` 启动，已运行时不要重复启动。使用 `ollama list` 确认模型。

首次准备：创建 backend/.venv，安装 requirements-dev.txt，配置 backend/.env，在 backend/ 执行 `python -m alembic upgrade head`，在 frontend/ 执行 `npm install`。Node.js/npm 需在 PATH 中。

在仓库根目录运行：

```powershell
.\start-signalradar.ps1 -CheckOnly
.\start-signalradar.ps1
```

脚本检查虚拟环境、.env、node_modules、Node/npm、数据库连通性、migration head（当前0010）、8000/3000 端口和本地 Ollama /api/tags。随后构建 Next.js，运行生产前端及单进程后端。只有构建与当前代码一致时才使用 -SkipBuild。脚本不会自动安装依赖、迁移数据库、启动 PostgreSQL / Ollama 或修改 Windows 配置。若执行策略阻止脚本，按本机允许的方式处理；脚本不会自行修改执行策略。

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
4. 激活后端虚拟环境，执行 `python -m alembic upgrade head`、`python -m alembic current`（0010 head）。
5. 创建 Topic 并扫描，在内容卡片点击“分析”，或“分析未处理内容”。先少量测试，本地模型可能较慢，单次后端调用超时为 180 秒。
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

目录自动创建且被 Git 忽略。每行是一条 UTF-8 JSON 事件，包含 UTC 时间戳、stage（item_analyze / digest / item_normalization / topic_match / event_relation / event_brief / brief_digest）、attempt、request_id、call_id 和 parent_request_id。每次 HTTP 尝试有独立 request_id；一次业务调用及其重试共享 call_id，第二次的 parent_request_id 指向第一次。Digest 事件还包含本次 item_count。

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
$latest = $events | Where-Object { $_.stage -in @('digest','brief_digest') -and $_.event -eq 'request' } | Select-Object -Last 1
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
2. 执行 `python -m alembic upgrade head`、`python -m alembic current`、`python -m alembic check`，确认 0010 head。
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

深度推理模型的 thinking 也消耗 num_predict。旧 Trace 中 2048 预算耗尽，出现 HTTP 200 但 content 为空；现 Digest 第一次 4096、重试 8192，每次 180 秒。空回复和超时有独立提示，完整原因查看 Trace。不要将 thinking 当作最终正文。v0.2.0 单条分析为 180 秒。

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


## 回收站验证

先停止旧后端并执行 `python -m alembic upgrade head`，确认 `alembic current` 为 `0010 (head)` 且 `alembic check` 无差异，然后启动应用。

1. 使用 MockSource 采集并分析，生成一条简报。
2. 对 Item 点击“移入回收站”，确认默认列表和首页计数减少；再次扫描不重新出现。
3. 进入 `/trash`，展开查看原文和 AI 摘要，点击“恢复”；刷新 Topic 确认 ID、分析和时间保持。
4. 对主题简报或 `/digests` 中的简报移入回收站，确认历史列表隐藏；恢复后可再次阅读完整正文。
5. 关闭并重新启动后端，确认回收站与已恢复记录均保持。
6. 再移入回收站，点击“永久删除”：取消确认不应删除，确认后无法恢复。永久删除 Item 后重新扫描可能再次采集。
7. Scheduler 或手动更新正在运行时，删除、恢复、永久删除应返回主题忙碌提示。回收站内容不参与自动分析或简报。

回收站不自动清空。Topic 删除仍永久级联删除其回收站内容，界面已明确提示。测试目录继续使用 `D:\pytest-temp` 下的新 GUID，并传入 `-p no:cacheprovider --basetemp`。


本次回收站验证结果：后端完整测试（含真实 PostgreSQL 集成测试）191 passed；前端 API 测试 8 passed；lint / build 通过；本机 PostgreSQL 已升级至 0005 (head)，Alembic check 无差异。测试不调用真实 AI / YouTube、不弹出 Windows 通知，PostgreSQL 测试新增数据通过外层事务回滚。旧运行进程尚未加载新增 API / 路由，需要重启 SignalRadar 后再进行上述浏览器交互验收。


## v0.2.0 本地验收

### 升级与安全准备

1. 保留现有 `.env`，先关闭 Scheduler 和通知。停止旧 SignalRadar 进程，确认 PostgreSQL / Ollama 已运行。
2. 使用与数据库版本匹配的 `pg_dump -Fc` 保存到本机私有目录，并用 `pg_restore --list` 校验。不要把备份或密码放进公开仓库。恢复备份会覆盖目标数据，需单独审查，不在日常验收自动执行。
3. 在 backend 虚拟环境执行 `python -m alembic upgrade head`、`python -m alembic current`、`python -m alembic check`，应为 `0010 (head)` 且无差异。迁移保留原数据，新增默认 0.80、规则表、分析解释/指纹、热度和来源快照。
4. `USE_MOCK_SOURCE=true` 仅模拟采集；分析仍调用 `OLLAMA_MODEL` 指定的本机模型。使用现有启动脚本构建并启动，不复用旧构建。

### Topic / Item / Digest

1. 创建 Topic：名称“ChatGPT”，描述关注模型发布和能力变化；添加包含条件、排除“主要讨论 GPT-5.6（仅比较提及不算）”，默认阈值 0.80。
2. 单独添加、编辑、停用和删除规则，保存后生效。相同包含/排除条件应提示冲突并进入 review。
3. 一键更新，展开实际搜索词；一般 1 条、内置特定模板最多 2 条，Mock 每查询 3 条。它不是正式新闻，不用 Mock 验证真实身份或热度。
4. 查看每条 Item 原始来源、发布时间与 AI 符合度、理由、排除状态、事实摘要。热度与符合度分开；Mock 热度必须未知。切换有效/无效/待复核/失败/待分析、最低符合度和排序。
5. 不符合或排除内容仍在数据库；uncertain 不自动进入简报。检查有效内容的中文简报、来源列表、同单元来源和安全外链。
6. 修改描述/阈值/启用规则，刷新内容确认旧分析标为 pending / analysis_stale；旧摘要可回看，但不直接用于新 Digest。高级操作可只分析待处理/过期内容，单条可主动重新分析。
7. 无变化再更新不重复分析/自动简报。相同事实仅评分/分类浮动不生成新简报。规则改变属于配置变化，重新确认后可生成对应简报。
8. 刷新、重启后数据与来源快照仍存在；旧简报没有 sources 时说明历史局限。回收站移入/恢复、永久删除确认保留原行为；恢复时规则若已变仍需重分析。

### 真实 YouTube 与配额

配置有效 `YOUTUBE_API_KEY`，`USE_MOCK_SOURCE=false`，第一次先只手动扫描一个 Topic。每 Scan 最多 2 search.list + 1 批量 videos.list，单次 HTTP 15 秒，无分页或网络重试。统计为实际计数，缺失 null，不是模型生成。查看 last_queries / warnings、数据库 popularity_metrics、UI 指标依据。外部网络或配额异常应明确显示，部分发现结果应保留。

平台搜索只能发现 metadata，不是完整视频理解；官方/粉丝身份不能仅凭频道名确认。符合度阈值不是模型准确率；热度公式、缺失处理与整合局限见 System Design。实际配额以 Google Cloud Console 和官方文档为准。

### Scheduler 与错误

手动流程通过后才启用 Scheduler，设置合理 SCAN_INTERVAL_MINUTES。应仅处理 enabled Topic、同规则下未完成/失败/过期内容；确认无变化不重复生成，并且同 Topic 不重入、单 Topic 错误不影响其他 Topic。通知仅在自动任务本轮有新有效内容且简报已保存时发送。

Ollama 不可用时 Raw Item 已保存，分析标 failed、已完成摘要仍保留。通过高级操作或单条 Analyze 重试，不要为了重试分析反复消耗 YouTube 查询配额。关停：Ctrl+C → SCHEDULER_ENABLED=false → 重启。

### 自动测试

所有自动测试使用 Fake Provider / MockTransport，不调用真实 AI / YouTube，不弹通知。每次测试创建 `D:\pytest-temp` 下的新 GUID 目录，并加 `-p no:cacheprovider --basetemp`，不要把系统 Temp 的 PermissionError 当业务错误。

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\Activate.ps1
$env:RUN_POSTGRES_TESTS='1'
$testTempPath = Join-Path 'D:\pytest-temp' ([guid]::NewGuid().ToString('N'))
python -m pytest -q --tb=short -p no:cacheprovider --basetemp $testTempPath
Remove-Item Env:\RUN_POSTGRES_TESTS
python -m alembic current
python -m alembic check
cd ..\frontend
npm run test:api
npm run lint
npm run build
```

真实模型与浏览器验收单独记录，不将 Fake AI 的固定符合度当真实模型质量证明。Trace 调试沿用上文开关、request_id 和私有内容保护约定。


v0.2.0 的 Analyze / Digest 均使用最多 24576 上下文；输入过长会明确失败，不静默丢规则。Item 预算 8192 / 超时 180 秒，Digest 4096 / 8192、最多一次 retry；较大 RAM/VRAM 与本地模型吞吐会影响耗时。Digest 指令已精简，正文输出说明、schema、错误来源编号、未知 URL 等被拒绝。当前年月不作为事件日期证据。

Topic 卡片的 analysis_state / analysis_counts 是当前持久化状态聚合，“最近成功分析”是成功时间，不伪造失败事件时间。规则变化后失败重分析仍保留历史摘要指纹和过期提示。


### v0.2.0 本机模型兼容与验收

当前本机配置名为 `deepseek-r1:8b`，但 `/api/show` 实际报告 family 为 `qwen3`（8.2B，Q4_K_M）。模型标签不能代表模型的实际控制能力；应以本机返回为准。`think=false` 探测仍产生 thinking，不据此假设推理已关闭。

新增可选 `OLLAMA_NO_THINK_HINT=false`。若模型支持 Qwen 风格 `/no_think` 提示，可设为 true 并重启：它仅在 system 指令前加入提示，不替换模型，不绕过 JSON / 事实校验，不增加 retry，不是安全边界，也不保证停止 thinking。当前本机私有 `.env` 已设为 true，其他凭据保持原值，文件仍被 Git 忽略。参考 [Qwen 官方说明](https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html)；模型能力与 Ollama 版本有关。

实际验收中，模型出现过输出预算耗尽、schema 回显、无来源年份；对应结果已被拒绝。最终当前 Provider 工厂使用一条明确标注“模拟”的资料，首轮 JSON 失败、一次重试后保存了中文简报和来源快照。此结果证明本地调用链可用，不代表所有新闻的语义质量已获保证。自动测试不依赖该真实模型。

一次 Analyze 最多 180 秒，一键更新最多 20 条；全量历史重分析可能耗时较长。建议先少量分析、核对理由，再开启 Scheduler；保持单个后端进程。条件涉及相对时间时，指纹不会随时钟自动变化，应主动重新分析检查时效。

完整结果、迁移备份与页面验收见 [v0.2.0 实施记录](v0.2.0-implementation.md)。


## Task A 单条简讯本地验收

1. 保留 `.env` 中真实模型与数据库配置，先关闭 Scheduler / 通知；备份后执行 `python -m alembic upgrade head`，current 应为 **0007 (head)**，check 无差异。
2. 启动 PostgreSQL、Ollama 与 SignalRadar，先 USE_MOCK_SOURCE=true 扫描测试 Topic。Mock 只模拟来源，规范化仍调用本机 Ollama。
3. Item 卡片中分别查看原始信息、既有 AI Analysis、AI 规范化简讯。点击“生成简讯”，检查中文标题/正文、人物机构、事件类型/时间、关键词、claims 和 warnings。
4. YouTube 必须提示只读取 metadata，未观看视频；reported 是来源声称，不是已证实。来源 URL 和 Item ID 应与原文一致。
5. 再点击读取已有简讯，应无新模型调用、相同 id/revision；刷新或重启后端仍可读取。更换 Topic 规则不应让 Topic 无关简讯失效。
6. 显式重新生成创建新修订，旧记录保留数据库。模型未启动/JSON失败时卡片显示失败可重试，原文、Analyze 和 Digest 不受影响。正常重复请求不自动重试成功结果。
7. Swagger 可测试 POST /api/topics/{id}/normalize?limit=3；逐条调用，不将多条文章塞入一个 Prompt。未接入 Scheduler，无新增自动开关需要开启。
8. Trace 开启后 stage=item_normalization，按 call_id/request_id 关联 request/response/validation_error/retry；原始数据可能私密，不能公开上传。默认关闭，不修改其他 AI Prompt。

模型请求沿用180秒超时和有界输出预算，最多一次解析/业务校验重试。简讯不是事实核验或未来 Event 聚类，不能据此将未经确认的私人关系/动机写成确定事实。

Windows 后端测试约定保持：每次 `D:\pytest-temp` 新 GUID、`--basetemp`、`-p no:cacheprovider`。运行完整后端、npm run test:api、npm run lint、npm run build，真实模型验收结果单独记录在 [Task A 记录](task-a-normalization.md)。


## Task B：事件与通知验收

1. 停止旧SignalRadar进程，保留.env并备份数据库。执行 `python -m alembic upgrade head` / current / check，应为 **0010 (head)** 且无差异。
2. Task C 起默认 EVENT_PROCESSING_ENABLED=true，每轮最多3条；如需只采集可显式设false；手动在Item简讯下点击“识别事件”。首次会复用或生成Task A简讯。需要Ollama时先启动Ollama，MockSource不模拟AI。
3. 打开 `/events`，查看事件类型/日期、原始链接数、当前关联Topic、来源声称与冲突、更新历史、依据和通知状态。
4. 可在Swagger对同一Item省略topic_id调用resolve，复用一次规范化结果匹配多个enabled Topic（最多50，建议指定Topic逐个验证）。改规则后旧匹配不自动有效，重新resolve后按当前指纹判断。
5. 开启自动阶段：EVENT_PROCESSING_ENABLED=true，重启；一键更新与Scheduler共用EventPipeline，每轮最多3条附加事件。旧Analyze/Digest仍独立，Task B通知不依赖Digest成功，不额外发送旧Digest通知。
6. 自动通知另需 SCHEDULER_ENABLED=true / NOTIFICATIONS_ENABLED=true。重复报道只增来源无通知；重要新事实才有候选；uncertain/冲突不自动推。disabled通知保持pending，发送前持久化sending；异常或中断不盲目重发，可能漏通知。停用自动：Ctrl+C，两个enabled开关设false并重启。
7. 一条失败原文仍保留，后续可重试；明确关系缓存复用，uncertain需单条retry=true。不要用反复扫描来重试事件AI。

### 可重复离线HTTP演示

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\python.exe scripts/demo_event_pipeline.py
```

使用Fake Source / Fake AI / Fake Notification与 D:\pytest-temp 下新GUID SQLite，通过真实FastAPI TestClient接口依次：创建Topic→扫描→规范化→匹配建事件→第二来源重复报道→第三来源售价进展→读取来源历史。预期一个Event、三个来源、两条Update、两次Fake通知（1→1→2），关闭/重连数据库后状态仍保留；不访问真实YouTube，不调用Ollama模型，不弹系统通知。脚本只在进程内关闭Scheduler/通知/Trace，不修改.env或正式数据库。

全量测试仍每次使用新GUID basetemp与 -p no:cacheprovider，开启RUN_POSTGRES_TESTS=1覆盖PostgreSQL；前端 npm run test:api / lint / build。Fake结果不能作为真实8B语义质量保证。当前匹配依赖有限别名、时间窗口和小模型，可能漏合并或误判，来源身份无证据时待复核。详见 [Task B记录](task-b-events.md)。


## Task C：阅读工作台本地验收

当前 migration head 为 `0010`；旧版章节里的较早 head 是历史状态。新版一键更新默认 `EVENT_PROCESSING_ENABLED=true`，已有 `.env` 显式 false 不会被自动覆盖，需主动修改后重启。`DIGEST_MAX_EVENTS=10`（1～20），另受11KB AI输入预算约束。Scheduler和通知仍默认关闭。

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m alembic current
python -m alembic check
# backend/.env: USE_MOCK_SOURCE=true, EVENT_PROCESSING_ENABLED=true
# 确认本地 ollama list 中的名称与 OLLAMA_MODEL 一致
uvicorn app.main:app --reload
# 另一个终端：
cd D:\Projects_ltl\Signal-Radar\frontend
npm run dev
```

1. PostgreSQL和Ollama启动后，创建Topic并执行一键更新。每轮最多3条待处理资料；查看保存阶段，积压未清空不应宣称没有新闻。先保持Scheduler关闭。
2. 阅读精准关注的简讯和匹配理由，展开真实来源，进入事件详情检查时间线/Brief版本。重复扫描不增加相同事件版本，重要新事实保留版本历史。
3. 至少2个有效AI完成Brief时可生成综合Digest；只有1个事件显示简讯集合。模型失败/非法输出也降级为集合，并明确不是AI综合成功。停止Ollama时采集仍可保存Raw，后续阶段失败明确显示。
4. 无新事件且当前检查完整时查看无更新报告。断网/数据库失败应显示失败；不能拿“无新事件”掩盖错误。手动只生成报告且没有扫描，不能声称扫描完成。
5. 进入开放发现，确认范围是已有事件库，按已读和来源多样性调整，不改变精准关注规则。标记已读后刷新仍保留；新Brief版本视为未读。
6. “重新综合当前主题”可重试先前模型综合失败，无需重新采集或规范化；历史报告继续可读。重启后端后检查Brief、版本、报告与最近运行记录。
7. Scheduler真实验收使用单进程、不使用reload。设置 SCHEDULER_ENABLED=true 和短测试间隔后重启；重复轮次不重复分析/生成相同事件，不重复发送已领取通知。测试后设false并重启。自动测试不弹真实Windows通知。

### 完全离线演示

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\python.exe scripts/demo_reading_workspace.py
# 如需浏览器：增加 --serve（占用127.0.0.1:8000），另启动前端
```

脚本使用 D:\pytest-temp 下新的GUID SQLite数据库、Fake AI / Fake Source / Fake Notification，通过实际HTTP接口验证三种结果、网络失败、不重复通知、读取和连接重建。不会修改正式数据库、.env，不消耗YouTube配额、不弹通知。页面里的模拟事实不是新闻，Fake模型结果不代表真实Ollama质量。

### Windows 自动测试约定（继续保留）

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
$env:RUN_POSTGRES_TESTS='1' # 需要本机PostgreSQL已迁移；写入包在回滚事务中
New-Item -ItemType Directory -Path D:\pytest-temp -Force | Out-Null
$testTempPath=Join-Path D:\pytest-temp ([guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $testTempPath
Remove-Item Env:\RUN_POSTGRES_TESTS
cd ..\frontend
npm run test:api
npm run lint
npm run build
```

每次测试使用新GUID，不复用默认 pytest-of-80538 目录。权限错误先定位环境原因，不修改业务/删测试或降低覆盖率。真实模型验收应另记模型、输入范围、耗时和降级情况，不能用Fake结果冒充真实YouTube/Ollama端到端通过。
