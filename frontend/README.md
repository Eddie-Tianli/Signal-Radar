# SignalRadar Frontend

Minimal Next.js frontend using React, TypeScript, Tailwind CSS, ESLint, and App Router.

Requires Node.js 20.9 or newer and npm.

From this directory:

```sh
npm install
npm run dev
```

Start the FastAPI backend at http://127.0.0.1:8000, then open http://localhost:3000. The homepage displays the backend status and API version.

Select **Manage Topics** or open http://localhost:3000/topics to view, create, edit, and delete topics. The page reports loading and request errors. Topic storage requires the PostgreSQL setup and migration described in [the backend README](../backend/README.md).

Checks:

```sh
npm run lint
npm run build
```

Use `npm ci` to install the exact dependency versions from `package-lock.json` on subsequent checkouts.
