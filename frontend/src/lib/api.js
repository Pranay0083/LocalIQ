import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lq_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const scoreTone = (score) => {
  if (score === null || score === undefined) return "muted";
  if (score >= 70) return "positive";
  if (score >= 45) return "warning";
  return "negative";
};

export const toneClass = {
  positive: "text-emerald-400",
  warning: "text-amber-400",
  negative: "text-red-400",
  muted: "text-zinc-500",
};

export const toneBg = {
  positive: "bg-emerald-500",
  warning: "bg-amber-500",
  negative: "bg-red-500",
  muted: "bg-zinc-700",
};

export const SOURCE_META = {
  live_api: { label: "Live API", cls: "text-blue-300 border-blue-500/40 bg-blue-500/10" },
  computed: { label: "Computed \u00b7 OSM", cls: "text-zinc-50 border-zinc-50/40 bg-zinc-50/10" },
  official: { label: "Official", cls: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" },
  media: { label: "News / Media", cls: "text-amber-300 border-amber-500/40 bg-amber-500/10" },
  community_verified: { label: "Community-verified", cls: "text-zinc-50 border-zinc-50/40 bg-zinc-50/10" },
  community_unverified: { label: "Community-unverified", cls: "text-slate-300 border-slate-500/40 bg-slate-500/10" },
  forum: { label: "Forum / Unverified", cls: "text-slate-400 border-slate-600/40 bg-slate-600/10" },
};

export const fmtDate = (value) => {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("en-IN", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return value;
  }
};

export const errMessage = (error) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return error?.message || "Something went wrong";
};
