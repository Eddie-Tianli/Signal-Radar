import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import ts from "typescript";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function api(fetch) {
  const source = fs.readFileSync(path.join(__dirname, "../app/topics/api.ts"), "utf8");
  const context = { exports: {}, fetch, AbortSignal, TextDecoder };
  vm.createContext(context);
  vm.runInContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, context);
  return context.exports;
}
const signal = () => new AbortController().signal;

test("one-click consumes fragmented UTF-8 progress and terminal result", async () => {
  const events = [{ status: "running", stage: "scan" }, { status: "completed", stage: "complete", digest: { title: "中文情报简报" } }];
  const bytes = new TextEncoder().encode(events.map(row => JSON.stringify(row)).join("\n") + "\n");
  const service = api(async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/topics/7/update");
    assert.equal(options.method, "POST");
    return new Response(new ReadableStream({ start(controller) { for (let i = 0; i < bytes.length; i += 2) controller.enqueue(bytes.slice(i, i + 2)); controller.close(); } }));
  });
  const seen = [];
  await service.updateTopic(7, signal(), row => seen.push(row));
  assert.equal(JSON.stringify(seen), JSON.stringify(events));
});

test("partial completion is a terminal result, not a successful full update", async () => {
  const service = api(async () => new Response(JSON.stringify({ status: "partial", stage: "analyze", failed_stage: "analyze", created: 3 }) + "\n"));
  let result;
  await service.updateTopic(1, signal(), row => { result = row; });
  assert.equal(result.status, "partial");
  assert.equal(result.created, 3);
});

test("truncated stream reports unknown status and does not invent completion", async () => {
  const service = api(async () => new Response('{"status":"running","stage":"analyze"}\n'));
  await assert.rejects(service.updateTopic(1, signal(), () => {}), /状态未知/);
});

test("duplicate Topic operation gives a clear retry-later message", async () => {
  const service = api(async () => new Response(JSON.stringify({ detail: "Topic operation already running. Wait and refresh." }), { status: 409 }));
  await assert.rejects(service.updateTopic(1, signal(), () => {}), /正在处理/);
});

test("empty Ollama response and timeout have distinct Chinese explanations", async () => {
  const empty = api(async () => new Response(JSON.stringify({ detail: "Ollama returned empty content. Check model output budget or try again." }), { status: 502 }));
  await assert.rejects(empty.generateDigest(1, signal()), /未返回简报正文/);
  const timeout = api(async () => new Response(JSON.stringify({ detail: "Ollama Digest timed out. Try again later." }), { status: 504 }));
  await assert.rejects(timeout.generateDigest(1, signal()), /简报生成超时/);
});

test("offline backend does not leak network details", async () => {
  const service = api(async () => { throw new Error("SECRET network detail"); });
  await assert.rejects(service.listTopics(), error => error.message.includes("后端无法连接") && !error.message.includes("SECRET"));
});


test("content deletion, trash restore and purge use distinct endpoints", async () => {
  const calls = [];
  const service = api(async (url, options) => {
    calls.push([url, options.method || "GET"]);
    return url.endsWith("/trash") ? new Response(JSON.stringify({ items: [], digests: [] })) : new Response(null, { status: 204 });
  });
  await service.moveToTrash("items", 12);
  await service.moveToTrash("digests", 13);
  assert.equal(JSON.stringify(await service.readTrash(signal())), '{"items":[],"digests":[]}');
  await service.restoreContent("items", 12);
  await service.permanentlyDelete("digests", 13);
  assert.deepEqual(calls, [
    ["http://127.0.0.1:8000/api/items/12", "DELETE"],
    ["http://127.0.0.1:8000/api/digests/13", "DELETE"],
    ["http://127.0.0.1:8000/api/trash", "GET"],
    ["http://127.0.0.1:8000/api/trash/items/12/restore", "POST"],
    ["http://127.0.0.1:8000/api/trash/digests/13", "DELETE"],
  ]);
});

test("missing deleted content gives a clear message", async () => {
  const service = api(async () => new Response(JSON.stringify({ detail: "内容不存在或已被永久删除。" }), { status: 404 }));
  await assert.rejects(service.moveToTrash("items", 12), /内容不存在或已被永久删除/);
});


test("Topic intent configuration preserves rule IDs and threshold in HTTP body", async () => {
  const input = { name: "ChatGPT", description: "关注模型发布", enabled: true, relevance_threshold: .85,
    include_rules: [{ id: 12, text: "主要讨论模型能力", enabled: true }], exclude_rules: [{ text: "主要讨论旧模型", enabled: false }] };
  const service = api(async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/topics/7");
    assert.equal(options.method, "PUT");
    assert.deepEqual(JSON.parse(options.body), input);
    return new Response(JSON.stringify({ id: 7, ...input }));
  });
  assert.equal((await service.saveTopic(input, 7)).relevance_threshold, .85);
});
