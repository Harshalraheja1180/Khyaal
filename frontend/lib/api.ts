export const API_ROOT = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) { super(message); this.name = "ApiError"; this.status = status; }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? sessionStorage.getItem("memorycare_token") : null;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let response: Response;
  try { response = await fetch(`${API_ROOT}${path}`, { ...init, headers, cache: "no-store" }); }
  catch { throw new ApiError("Could not reach Khyaal. Check that the API is running and try again."); }
  if (response.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/login") && !path.startsWith("/auth/register")) {
    sessionStorage.removeItem("memorycare_token");
    window.dispatchEvent(new Event("memorycare:session-expired"));
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); message = Array.isArray(body.detail) ? body.detail.map((x: { msg?: string }) => x.msg).join("; ") : body.detail || message; } catch { /* use status text */ }
    throw new ApiError(String(message), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function mediaUrl(id: string): Promise<string> {
  const token = sessionStorage.getItem("memorycare_token");
  const response = await fetch(`${API_ROOT}/media/${id}/content`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new ApiError("This private photo is not available.", response.status);
  return URL.createObjectURL(await response.blob());
}

export async function uploadMedia(dependentId: string, file: File, category: string) {
  const form = new FormData(); form.append("file", file); form.append("category", category);
  return api<{ id: string; filename: string; content_type: string; size_bytes: number }>(`/dependents/${dependentId}/media`, { method: "POST", body: form });
}

export type User = { id: string; email: string; display_name: string; roles: string[] };
export type Dependent = { id: string; display_name: string; preferred_name: string | null; permissions: string[] };
export type Profile = { id: string; user_id: string; preferred_name: string; mode: "OLDER_ADULT" | "MEMORY_SUPPORT"; timezone: string; locale: string; age_band?: string | null };
export type Medicine = { id: string; dependent_id: string; name: string; instructions?: string | null; schedule: Record<string, unknown>; active: boolean };
export type Reminder = { id: string; dependent_id: string; title: string; kind: string; schedule: Record<string, unknown>; active: boolean };
export type Appointment = { id: string; dependent_id: string; title: string; starts_at: string; location_label?: string | null; notes?: string | null };
export type Contact = { id: string; dependent_id: string; name: string; relationship_label: string; phone: string; priority: number };
export type MemoryEntry = { id: string; name: string; description?: string | null; relationship_label?: string | null; media_id?: string | null };
export type Quiz = { id: string; dependent_id: string; title: string; active: boolean; difficulty?: string; questions?: QuizQuestion[] };
export type QuizQuestion = { id: string; prompt: string; image_media_id?: string | null; audio_media_id?: string | null; position: number; options: QuizOption[] };
export type QuizOption = { id: string; label: string; image_media_id?: string | null; is_correct?: boolean; position: number };
export type Game = { id: string; dependent_id: string; title: string; game_type: string; configuration: Record<string, unknown>; active: boolean };
export type Alert = { id: string; alert_type: string; severity: string; status: string; message: string; created_at?: string };
export type Notification = { id: string; notification_type: string; title: string; message: string; is_read: boolean; created_at: string; guardian_link_id: string | null };
