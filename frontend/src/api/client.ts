/**
 * Typed fetch wrappers for the FastAPI backend.
 *
 * All requests go to same-origin paths (`/api/...`, `/files/...`):
 *  - In dev, Vite proxies them to http://127.0.0.1:8000 (see astro.config.mjs).
 *  - In production (Phase 8), a reverse proxy routes the same paths.
 */

import type {
  ExportFormat,
  GenerateSettings,
  JobInfo,
  JobStatus,
} from "@/types/settings";

interface EnqueueResponse {
  job_id: string;
  status: JobStatus;
}

export async function postPreview(file: File, settings: GenerateSettings): Promise<string> {
  return enqueue("/api/v1/preview", file, settings);
}

export async function postExport(
  file: File,
  settings: GenerateSettings,
  fmt: ExportFormat,
): Promise<string> {
  return enqueue("/api/v1/export", file, settings, fmt);
}

async function enqueue(
  path: string,
  file: File,
  settings: GenerateSettings,
  fmt?: ExportFormat,
): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("settings", JSON.stringify(settings));
  if (fmt) fd.append("format", fmt);
  const r = await fetch(path, { method: "POST", body: fd });
  if (!r.ok) throw await apiError(r);
  const data = (await r.json()) as EnqueueResponse;
  return data.job_id;
}

export async function getJob(jobId: string): Promise<JobInfo> {
  const r = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
  if (!r.ok) throw await apiError(r);
  return (await r.json()) as JobInfo;
}

interface PollOptions {
  intervalMs?: number;
  signal?: AbortSignal;
  onUpdate?: (info: JobInfo) => void;
}

/** Poll a job until it reaches a terminal state. Throws AbortError if cancelled. */
export async function pollJob(jobId: string, opts: PollOptions = {}): Promise<JobInfo> {
  const interval = opts.intervalMs ?? 1000;
  while (true) {
    if (opts.signal?.aborted) {
      throw new DOMException("poll aborted", "AbortError");
    }
    const info = await getJob(jobId);
    opts.onUpdate?.(info);
    if (info.status === "completed" || info.status === "failed") return info;
    await sleep(interval, opts.signal);
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function apiError(r: Response): Promise<Error> {
  let detail: unknown;
  try {
    detail = await r.json();
  } catch {
    detail = await r.text();
  }
  const body = typeof detail === "string" ? detail : JSON.stringify(detail);
  return new Error(`HTTP ${r.status}: ${body}`);
}
