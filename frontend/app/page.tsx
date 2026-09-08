"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type ApiStatus = {
  name: string;
  version: string;
  status: string;
};

export default function Home() {
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 5000);

    async function loadStatus() {
      try {
        const response = await fetch("http://127.0.0.1:8000/api/status", {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Status request failed: ${response.status}`);
        }

        const data = await response.json();
        if (
          !data ||
          typeof data.name !== "string" ||
          typeof data.version !== "string" ||
          typeof data.status !== "string"
        ) {
          throw new Error("Invalid status response");
        }
        if (active) setApiStatus(data);
      } catch {
        if (active) setError(true);
      } finally {
        clearTimeout(timeout);
      }
    }

    void loadStatus();
    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center text-slate-900">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">SignalRadar</h1>
      <p className="text-lg text-slate-600">
        Personal Information Intelligence Platform
      </p>
      <div aria-live="polite" className="space-y-2">
        {error ? (
          <p role="alert" className="text-red-700">
            Backend: unavailable. Please check the backend and refresh.
          </p>
        ) : apiStatus ? (
          <>
            <p className="text-emerald-800">Backend: {apiStatus.status}</p>
            <p className="text-slate-600">API Version: {apiStatus.version}</p>
          </>
        ) : (
          <p className="text-slate-600">Backend: loading...</p>
        )}
      </div>
      <Link href="/topics" className="rounded-lg bg-slate-900 px-5 py-3 text-white hover:bg-slate-700">
        Manage Topics
      </Link>
    </main>
  );
}
