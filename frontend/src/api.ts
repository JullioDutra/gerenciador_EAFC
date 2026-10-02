import { useEffect, useState } from "react";
export const getToken = () => localStorage.getItem("token");
export const setToken = (t: string | null) => (t ? localStorage.setItem("token", t) : localStorage.removeItem("token"));

export async function api(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}) {
  const h: Record<string, string> = {}; const t = getToken();
  if (t) h.Authorization = `Token ${t}`;
  if (opts.body) h["Content-Type"] = "application/json";
  const r = await fetch(`/api${path}`, { method: opts.method ?? "GET", headers: h,
    body: opts.form ?? (opts.body ? JSON.stringify(opts.body) : undefined) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Não foi possível concluir a ação.");
  return data;
}
/** Baixa um arquivo (ex.: PNG) com o token — <img src> não manda o header Authorization. */
export async function apiBlob(path: string): Promise<Blob> {
  const t = getToken();
  const r = await fetch(`/api${path}`, { headers: t ? { Authorization: `Token ${t}` } : {} });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Não foi possível gerar a imagem.");
  return r.blob();
}
export async function apiForm(path: string, form: FormData, method = "POST") {
  return api(path, { method, form });
}
export function useData<T = any>(path: string | null) {
  const [d, setD] = useState<T>(); const [n, setN] = useState(0); const [err, setErr] = useState("");
  useEffect(() => { if (path) api(path).then(setD).catch((e) => setErr(e.message)); }, [path, n]);
  return { data: d, err, reload: () => setN((x) => x + 1) };
}
