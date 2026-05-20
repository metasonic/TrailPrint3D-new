export interface JobAccepted {
  job_id: string;
}

export type JobState = "pending" | "processing" | "completed" | "failed";

export interface JobStatus {
  job_id: string;
  status: JobState;
  progress: number;
  result_url: string | null;
  error: string | null;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res;
}

export async function submitPreview(
  gpxFile: File,
  settings: Record<string, unknown>,
): Promise<JobAccepted> {
  const body = new FormData();
  body.append("gpx_file", gpxFile);
  body.append("settings_json", JSON.stringify(settings));
  const res = await apiFetch("/api/v1/preview", { method: "POST", body });
  return res.json() as Promise<JobAccepted>;
}

export async function submitExport(
  gpxFile: File,
  settings: Record<string, unknown>,
  format: string,
): Promise<JobAccepted> {
  const body = new FormData();
  body.append("gpx_file", gpxFile);
  body.append("settings_json", JSON.stringify(settings));
  body.append("format", format);
  const res = await apiFetch("/api/v1/export", { method: "POST", body });
  return res.json() as Promise<JobAccepted>;
}

export function pollJob(
  jobId: string,
  onUpdate: (s: JobStatus) => void,
  intervalMs = 2000,
  timeoutMs = 5 * 60 * 1000,
): Promise<JobStatus> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;

    const tick = async () => {
      if (Date.now() > deadline) {
        reject(new Error("Job timed out after 5 minutes"));
        return;
      }
      let status: JobStatus;
      try {
        const res = await apiFetch(`/api/v1/jobs/${jobId}`);
        status = (await res.json()) as JobStatus;
      } catch (e) {
        reject(e);
        return;
      }
      onUpdate(status);
      if (status.status === "completed") {
        resolve(status);
      } else if (status.status === "failed") {
        reject(new Error(status.error ?? "Job failed"));
      } else {
        setTimeout(tick, intervalMs);
      }
    };

    tick();
  });
}
