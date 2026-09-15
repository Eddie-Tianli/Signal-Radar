# SignalRadar 前端

使用 Next.js、React、TypeScript、Tailwind CSS、ESLint 和 App Router。需要 Node.js 20.9 或更高版本及 npm。

在 frontend/ 中运行：

```sh
npm install
npm run dev
```

启动位于 http://127.0.0.1:8000 的 FastAPI 后端，再访问 http://localhost:3000。
v0.1.0 首页“概览”显示统计、近期内容、最新简报和本地依赖状态，通过导航进入“主题”。

http://localhost:3000/topics 支持创建、编辑、删除主题，扫描、分析内容及生成简报，并提供加载与错误提示。持久化需要完成 [后端说明](../backend/README.md) 中的 PostgreSQL 配置和 migration。

界面以中文为主，保留 SignalRadar、Ollama、AI、source 标识等技术术语。API 字段、变量、用户输入和 AI 输出不翻译；已知后端错误在前端映射为中文。

验证命令：

```sh
npm run lint
npm run build
```

后续 checkout 可使用 `npm ci` 按 package-lock.json 安装精确版本。
