export type Topic = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
};

export type TopicInput = Omit<Topic, "id">;

const baseUrl = "http://127.0.0.1:8000/api/topics";

async function request(path = "", options: RequestInit = {}, timeoutMs = 5000) {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      cache: "no-store",
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(timeoutMs)])
        : AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new Error("Cannot reach the backend. Check that it is running and try again.");
  }
  if (!response.ok) {
    if (path.endsWith("/scan") || path.endsWith("/items")) {
      const body = await response.json().catch(() => null);
      throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (HTTP ${response.status}).`);
    }
    if (response.status === 404) {
      throw new Error("This topic no longer exists. Refresh the list.");
    }
    if (response.status === 422) {
      throw new Error("Invalid topic. Please enter a non-empty name and check the fields.");
    }
    throw new Error(`Request failed (HTTP ${response.status}). Please try again.`);
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
