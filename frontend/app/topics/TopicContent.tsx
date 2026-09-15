"use client";

import { useEffect, useRef, useState } from "react";
import { analyzeItem, analyzeTopic, listItems, scanTopic, type AnalysisBatchResult, type CollectedItem, type ScanResult } from "./api";
import ItemList from "./ItemList";
import TopicDigests from "./TopicDigests";

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
  const [analyzing, setAnalyzing] = useState<Record<number, boolean>>({});
  const [analysisErrors, setAnalysisErrors] = useState<Record<number, string>>({});
  const [batchAnalyzing, setBatchAnalyzing] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<AnalysisBatchResult | null>(null);
  const analysisControllers = useRef(new Map<number, AbortController>());
  const batchController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controllers = analysisControllers.current;
    return () => {
      controllers.forEach((controller) => controller.abort());
      batchController.current?.abort();
    };
  }, []);

  async function analyze(id: number) {
    if (analysisControllers.current.has(id) || batchController.current) return;
    const controller = new AbortController();
    analysisControllers.current.set(id, controller);
    setAnalyzing((previous) => ({ ...previous, [id]: true }));
    setAnalysisErrors((previous) => ({ ...previous, [id]: "" }));
    try {
      const updated = await analyzeItem(id, controller.signal);
      if (!controller.signal.aborted) setItems((previous) => previous.map((item) => item.id === id ? updated : item));
    } catch (error) {
      if (!controller.signal.aborted) setAnalysisErrors((previous) => ({ ...previous,
        [id]: error instanceof Error ? error.message : "Check the backend and local Ollama service." }));
    } finally {
      analysisControllers.current.delete(id);
      if (!controller.signal.aborted) setAnalyzing((previous) => ({ ...previous, [id]: false }));
    }
  }

  async function analyzeBatch() {
    if (batchController.current || analysisControllers.current.size) return;
    const controller = new AbortController();
    batchController.current = controller;
    setBatchAnalyzing(true);
    setBatchError(null);
    setBatchResult(null);
    try {
      const result = await analyzeTopic(topicId, controller.signal);
      if (!controller.signal.aborted) setBatchResult(result);
    } catch (error) {
      if (!controller.signal.aborted) setBatchError(error instanceof Error ? error.message : "Check the backend and local Ollama service.");
    } finally {
      batchController.current = null;
      if (!controller.signal.aborted) {
        setBatchAnalyzing(false);
        // Earlier successes may have been committed even if the batch failed.
        refreshItems();
      }
    }
  }

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
        <button onClick={() => void scan()} disabled={scanning || batchAnalyzing || Object.values(analyzing).some(Boolean)} className="rounded-lg bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
          {scanning ? "Scanning..." : "Scan"}
        </button>
        <button onClick={refreshItems} disabled={loading || scanning || batchAnalyzing || Object.values(analyzing).some(Boolean)} className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-50">
          {open ? "Refresh items" : "View items"}
        </button>
        <button onClick={() => void analyzeBatch()} disabled={batchAnalyzing || loading || scanning || Object.values(analyzing).some(Boolean)}
          className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-50">
          {batchAnalyzing ? "Analyzing unprocessed items..." : "Analyze Unprocessed Items"}
        </button>
      </div>
      <div aria-live="polite" className="mt-3 space-y-3">
        {result && <p className="text-sm text-emerald-700">Fetched: {result.fetched} · New: {result.created} · Duplicates: {result.duplicates}</p>}
        {scanError && <p role="alert" className="text-sm text-red-700">Scan failed: {scanError}</p>}
        {batchAnalyzing && <p role="status" className="text-sm">Analyzing up to 10 items sequentially. This may take several minutes.</p>}
        {batchError && <p role="alert" className="text-sm text-red-700">Batch analysis failed: {batchError}</p>}
        {batchResult && <p className="text-sm">Processed: {batchResult.processed} · Relevant: {batchResult.relevant} · Irrelevant: {batchResult.irrelevant} · Failed: {batchResult.failed}</p>}
        {!!batchResult?.failed && <p role="alert" className="text-sm text-red-700">Some items could not be analyzed. Check local Ollama, or Analyze an individual item for details.</p>}
        {open && (loading ? <p role="status">Loading items...</p> : error ? <p role="alert" className="text-sm text-red-700">Could not load items: {error}</p> : <ItemList items={items} analyzing={analyzing} errors={analysisErrors} batchAnalyzing={batchAnalyzing || scanning} onAnalyze={(id) => void analyze(id)} />)}
      </div>
      <TopicDigests topicId={topicId} />
    </section>
  );
}
