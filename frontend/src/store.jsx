import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { api, token } from "./api";

const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [meta, setMeta] = useState({ ai_enabled: false, llm_provider: "offline", llm_model: "" });
  const [toasts, setToasts] = useState([]);
  const [theme, setTheme] = useState(document.documentElement.classList.contains("dark") ? "dark" : "light");

  useEffect(() => {
    api.get("/api/meta").then(setMeta).catch(() => {});
    if (!token.get()) return setReady(true);
    api.get("/api/auth/me").then(setUser).catch(() => token.set(null)).finally(() => setReady(true));
  }, []);

  const toast = useCallback((message, kind = "info") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const value = useMemo(() => ({
    user, setUser, ready, meta, toast, theme,
    async signIn(path, body) {
      const data = await api.post(path, body);
      token.set(data.token);
      setUser(data.user);
      return data.user;
    },
    signOut() { token.set(null); setUser(null); },
    refreshUser: () => api.get("/api/auth/me").then(setUser).catch(() => {}),
    toggleTheme() {
      const next = theme === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      localStorage.setItem("theme", next);
      setTheme(next);
    },
  }), [user, ready, meta, toast, theme]);

  const icons = { success: CheckCircle2, error: AlertTriangle, info: Info };
  const tones = { success: "text-emerald-500", error: "text-rose-500", info: "text-brand" };
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {toasts.map((t) => {
          const Icon = icons[t.kind] || Info;
          return (
            <div key={t.id} className="card pointer-events-auto flex max-w-md animate-rise items-start gap-2.5 px-4 py-3 text-sm">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tones[t.kind]}`} />
              <span>{t.message}</span>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

/** Load data for a page: returns {data, error, loading, reload, setData}. */
export function useLoad(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    return api.get(path)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => setState({ data: null, error: e.message, loading: false }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load, setData: (data) => setState((s) => ({ ...s, data })) };
}
