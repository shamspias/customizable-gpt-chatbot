// Minimal API client. SSE endpoints are POST (bodies), so native EventSource
// can't be used — we read the fetch stream and parse SSE frames by hand.
//
// Auth: a bearer token (persisted in localStorage) is attached to every request.
// A 401 *while a token is set* means the session expired — we clear it and emit a
// `veldra:unauthorized` event so the shell can fall back to the sign-in screen.

export type SseHandler = (event: string, data: any) => void;

const TOKEN_KEY = "veldra.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra };
}

function onUnauthorized(): void {
  // Only a *had-a-token* 401 is a real expiry (a failed login has no token yet).
  if (getToken()) {
    clearToken();
    window.dispatchEvent(new CustomEvent("veldra:unauthorized"));
  }
}

/** fetch() with the auth header injected and global 401 handling. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = authHeaders((init.headers as Record<string, string>) || {});
  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401) onUnauthorized();
  return resp;
}

// Abort a stream if no bytes arrive for this long. The server pings (SSE comments)
// every ~15s, so a healthy run resets this continuously; only a truly stalled
// connection trips it — surfacing an error instead of a frozen UI.
const STREAM_IDLE_MS = 90_000;

export async function streamPost(
  path: string,
  body: unknown,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  const ctrl = new AbortController();
  if (signal) signal.addEventListener("abort", () => ctrl.abort(), { once: true });
  let idle: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    clearTimeout(idle);
    idle = setTimeout(() => ctrl.abort(new DOMException("stream idle timeout", "TimeoutError")), STREAM_IDLE_MS);
  };
  arm();
  try {
    const resp = await fetch(path, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (resp.status === 401) onUnauthorized();
    if (!resp.ok || !resp.body) {
      throw new Error(`request failed: ${resp.status} ${await resp.text()}`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      arm(); // reset idle timer on every chunk (including heartbeats)
      if (done) break;
      buf = (buf + decoder.decode(value, { stream: true })).replace(/\r/g, "");
      let sep: number;
      while ((sep = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        let event = "message";
        let data = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith(":")) continue; // heartbeat / comment
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) onEvent(event, JSON.parse(data));
      }
    }
  } finally {
    clearTimeout(idle);
  }
}

export async function postJson<T = any>(path: string, body: unknown): Promise<T> {
  const r = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getJson<T = any>(path: string): Promise<T> {
  const r = await apiFetch(path);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function uploadFile(file: File): Promise<any> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch("/api/kb/upload", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
