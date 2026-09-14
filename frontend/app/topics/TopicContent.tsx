"use client";

import { useEffect, useRef, useState } from "react";
import { listItems, scanTopic, type CollectedItem, type ScanResult } from "./api";
import ItemList from "./ItemList";

export default function TopicContent({ topicId }: { topicId: number }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CollectedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [revision, setRevision] = useState(0);
  const scanController = useRef<AbortController | null>(null);

  useEffect(() => () => scanController.current?.abort(), []);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    // Run state updates with the asynchronous request, not synchronously in the effect.
    void (async () => {
      try {
        const data = await listItems(topicId, controller.signal);
        if (!controller.signal.aborted) setItems(data);
      } catch (error) {
        if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "Could not load items.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [open, revision, topicId]);

  function refreshItems() {
    setLoading(true);
    setError(null);
    setOpen(true);
    setRevision((value) => value + 1);
  }

  async function scan() {
    if (scanController.current) return;
    const controller = new AbortController();
    scanController.current = controller;
    setScanning(true);
    setScanError(null);
    setResult(null);
    try {
      const data = await scanTopic(topicId, controller.signal);
      if (!controller.signal.aborted) {
        setResult(data);
        refreshItems();
      }
    } catch (error) {
      if (!controller.signal.aborted) setScanError(error instanceof Error ? error.message : "Scan failed.");
    } finally {
      scanController.current = null;
      if (!controller.signal.aborted) setScanning(false);
    }
  }

  return (
    <section aria-label={`Collected items for Topic ${topicId}`} className="mt-5 border-t border-slate-200 pt-4">
      <div className="flex flex-wrap gap-3">
        <button onClick={() => void scan()} disabled={scanning} className="rounded-lg bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
          {scanning ? "Scanning..." : "Scan"}
        </button>
        <button onClick={refreshItems} disabled={loading} className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-50">
          {open ? "Refresh items" : "View items"}
        </button>
      </div>
      <div aria-live="polite" className="mt-3 space-y-3">
        {result && <p className="text-sm text-emerald-700">Fetched: {result.fetched} · New: {result.created} · Duplicates: {result.duplicates}</p>}
        {scanError && <p role="alert" className="text-sm text-red-700">Scan failed: {scanError}</p>}
        {open && (loading ? <p role="status">Loading items...</p> : error ? <p role="alert" className="text-sm text-red-700">Could not load items: {error}</p> : <ItemList items={items} />)}
      </div>
    </section>
  );
}
