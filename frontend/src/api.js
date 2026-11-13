// Small fetch wrapper: attaches the JWT, parses JSON and surfaces API error messages.
const BASE = import.meta.env.VITE_API_URL || "";

export const token = {
  get: () => localStorage.getItem("token"),
  set: (t) => (t ? localStorage.setItem("token", t) : localStorage.removeItem("token")),
};

async function request(method, path, body, isForm = false) {
  const headers = {};
  if (token.get()) headers.Authorization = `Bearer ${token.get()}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  if (res.status === 401 && token.get() && !path.startsWith("/api/auth/log")) {
    token.set(null);
    window.location.assign("/login");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join("; ");
    } catch {}
    throw new Error(message);
  }
  return res;
}

export const api = {
  get: (p) => request("GET", p).then((r) => r.json()),
  post: (p, b) => request("POST", p, b ?? {}).then((r) => r.json()),
  put: (p, b) => request("PUT", p, b).then((r) => r.json()),
  patch: (p, b) => request("PATCH", p, b).then((r) => r.json()),
  del: (p) => request("DELETE", p).then((r) => r.json()),
  form: (p, formData) => request("POST", p, formData, true).then((r) => r.json()),
  async download(path, fallbackName) {
    const res = await request("GET", path);
    const blob = await res.blob();
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || fallbackName;
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
