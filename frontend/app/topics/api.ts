export type Topic = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
};

export type TopicInput = Omit<Topic, "id">;

const baseUrl = "http://127.0.0.1:8000/api/topics";

async function request(path = "", options: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      cache: "no-store",
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(5000)])
        : AbortSignal.timeout(5000),
    });
  } catch {
    throw new Error("Cannot reach the backend. Check that it is running and try again.");
  }
  if (!response.ok) {
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
