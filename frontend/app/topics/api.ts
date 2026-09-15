export type Topic = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
};

export type TopicInput = Omit<Topic, "id">;

// 只转换展示文案，不改变后端响应、HTTP 状态或请求参数。
const errorMessages: Record<string, string> = {
  "Topic not found": "主题不存在，请刷新列表。",
  "Item not found": "内容不存在，请刷新列表。",
  "Set OLLAMA_MODEL to an installed local model name.": "请将 OLLAMA_MODEL 配置为本机已安装的模型名称。",
  "OLLAMA_BASE_URL must be a local loopback HTTP address.": "OLLAMA_BASE_URL 必须使用本机回环 HTTP 地址。",
  "Ollama analysis timed out. Try one Item again.": "Ollama 分析超时，请稍后单独重试该条内容。",
  "Cannot connect to local Ollama. Check that it is running.": "无法连接本地 Ollama，请确认 Ollama 已启动。",
  "Ollama model or endpoint not found. Check OLLAMA_MODEL and ollama list.": "未找到 Ollama 模型或接口，请检查 OLLAMA_MODEL，并运行 ollama list 确认模型已安装。",
  "Ollama analysis failed. Check the local Ollama service.": "Ollama 调用失败，请检查本地服务。",
  "Ollama returned invalid structured analysis. Retry or check model support.": "Ollama 返回的数据格式不符合要求，请重试或检查模型是否支持结构化输出。",
  "This AI provider does not support Digests.": "当前 AIProvider 不支持生成简报。",
  "Could not save or read analysis. Check the database.": "分析结果读取或保存失败，请检查数据库。",
  "Could not save scan results. Check the database and retry.": "扫描结果保存失败，请检查数据库后重试。",
  "Could not read items. Check the database and retry.": "内容读取失败，请检查数据库后重试。",
  "Could not read or save Digest. Check the database.": "简报读取或保存失败，请检查数据库。",
  "No analyzed relevant Items are available for a Digest.": "暂无可用于生成简报的相关内容，请先完成内容分析。",
  "AI returned an invalid structured Digest.": "AI 返回的简报格式不符合要求，请重试。",
  "YouTube is not configured: set YOUTUBE_API_KEY on the backend.": "尚未配置 YouTube，请在后端设置 YOUTUBE_API_KEY；本地测试可启用 USE_MOCK_SOURCE。",
  "YouTube request timed out. Try again later.": "YouTube 请求超时，请稍后重试。",
  "Could not connect to YouTube. Try again later.": "无法连接 YouTube，请检查网络后重试。",
  "YouTube rejected the request. Check API enablement, key restrictions, and quota.": "YouTube 拒绝了请求，请检查 API 是否启用、Key 限制和配额。",
  "YouTube request failed. Check API configuration or try again later.": "YouTube 请求失败，请检查 API 配置或稍后重试。",
  "YouTube returned an invalid search response.": "YouTube 返回的数据格式不符合要求，请稍后重试。"
};

const baseUrl = "http://127.0.0.1:8000/api/topics";

async function request(path = "", options: RequestInit = {}, timeoutMs = 5000, base = baseUrl) {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...options,
      cache: "no-store",
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(timeoutMs)])
        : AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new Error("后端无法连接或请求超时，请确认服务正在运行后重试。");
  }
  if (!response.ok) {
    if (path.endsWith("/scan") || path.endsWith("/items") || path.includes("/analyze") || path.includes("/digest")) {
      const body = await response.json().catch(() => null);
      throw new Error((typeof body?.detail === "string" ? errorMessages[body.detail] : undefined) ?? `请求失败（HTTP ${response.status}），请检查服务状态后重试。`);
    }
    if (response.status === 404) {
      throw new Error("该主题已不存在，请刷新列表。");
    }
    if (response.status === 422) {
      throw new Error("主题信息无效，请填写非空名称并检查其他字段。");
    }
    throw new Error(`请求失败（HTTP ${response.status}），请稍后重试。`);
  }
  return response;
}

export async function listTopics(signal?: AbortSignal): Promise<Topic[]> {
  return (await request("", { signal })).json();
}

export async function saveTopic(data: TopicInput, id?: number): Promise<Topic> {
  return (await request(id === undefined ? "" : `/${id}`, {
    method: id === undefined ? "POST" : "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })).json();
}

export async function deleteTopic(id: number): Promise<void> {
  await request(`/${id}`, { method: "DELETE" });
}

export type CollectedItem = {
  id: number; topic_id: number; source: string; external_id: string;
  title: string; url: string; author: string | null;
  published_at: string | null; snippet: string | null; collected_at: string;
  ai_relevant: boolean | null;
  ai_relevance_score: number | null;
  ai_category: string | null;
  ai_summary: string | null;
  ai_analyzed_at: string | null;
};

export type ScanResult = {
  topic_id: number; source: string; fetched: number; created: number; duplicates: number;
};

export async function listItems(id: number, signal: AbortSignal): Promise<CollectedItem[]> {
  return (await request(`/${id}/items`, { signal })).json();
}

export async function scanTopic(id: number, signal: AbortSignal): Promise<ScanResult> {
  // A scan includes the upstream YouTube request and database writes.
  return (await request(`/${id}/scan`, { method: "POST", signal }, 60000)).json();
}

export type AnalysisBatchResult = {
  topic_id: number; processed: number; relevant: number; irrelevant: number; failed: number;
};

export async function analyzeItem(id: number, signal: AbortSignal): Promise<CollectedItem> {
  return (await request(`/${id}/analyze`, { method: "POST", signal }, 150000,
    "http://127.0.0.1:8000/api/items")).json();
}

export async function analyzeTopic(id: number, signal: AbortSignal): Promise<AnalysisBatchResult> {
  // Up to ten sequential model calls, each with a backend timeout of 120 seconds.
  return (await request(`/${id}/analyze?limit=10`, { method: "POST", signal }, 1250000)).json();
}

export type Digest = {
  id: number; topic_id: number; title: string; summary: string;
  item_count: number; generated_at: string;
};

export async function generateDigest(id: number, signal: AbortSignal): Promise<Digest> {
  return (await request(`/${id}/digest`, { method: "POST", signal }, 150000)).json();
}

export async function listDigests(id: number, signal: AbortSignal): Promise<Digest[]> {
  return (await request(`/${id}/digests`, { signal })).json();
}
