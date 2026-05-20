import { afterEach, describe, expect, it, vi } from "vitest";
import { getJob, pollJob, postExport, postPreview } from "@/api/client";
import { DEFAULT_SETTINGS } from "@/types/settings";

const FETCH = globalThis.fetch;

function mockFetch(impl: (req: Request | string, init?: RequestInit) => Promise<Response>) {
  globalThis.fetch = vi.fn(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    return impl(url, init as RequestInit);
  }) as unknown as typeof fetch;
}

afterEach(() => {
  globalThis.fetch = FETCH;
  vi.useRealTimers();
});

describe("postPreview", () => {
  it("POSTs multipart with file + settings JSON", async () => {
    let captured: { url: string; method?: string; body?: FormData } = { url: "" };
    mockFetch(async (url, init) => {
      captured = { url: String(url), method: init?.method, body: init?.body as FormData };
      return new Response(JSON.stringify({ job_id: "abc-123", status: "pending" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    const file = new File(["<gpx/>"], "x.gpx", { type: "application/gpx+xml" });
    const id = await postPreview(file, DEFAULT_SETTINGS);
    expect(id).toBe("abc-123");
    expect(captured.url).toBe("/api/v1/preview");
    expect(captured.method).toBe("POST");
    expect(captured.body?.get("file")).toBeInstanceOf(File);
    expect(captured.body?.get("settings")).toBe(JSON.stringify(DEFAULT_SETTINGS));
    expect(captured.body?.get("format")).toBeNull();
  });

  it("throws on HTTP error with the response body", async () => {
    mockFetch(async () => new Response(JSON.stringify({ detail: "bad" }), { status: 422 }));
    const file = new File(["<gpx/>"], "x.gpx");
    await expect(postPreview(file, DEFAULT_SETTINGS)).rejects.toThrow(/HTTP 422/);
  });
});

describe("postExport", () => {
  it("adds the format field", async () => {
    let body: FormData | undefined;
    mockFetch(async (_url, init) => {
      body = init?.body as FormData;
      return new Response(JSON.stringify({ job_id: "j", status: "pending" }), { status: 200 });
    });
    const file = new File([""], "x.gpx");
    await postExport(file, DEFAULT_SETTINGS, "stl");
    expect(body?.get("format")).toBe("stl");
  });
});

describe("getJob", () => {
  it("encodes the job id in the path", async () => {
    let captured = "";
    mockFetch(async (url) => {
      captured = String(url);
      return new Response(
        JSON.stringify({ job_id: "weird id", status: "completed", result_url: "/files/x.glb", error: null }),
        { status: 200 },
      );
    });
    const info = await getJob("weird id");
    expect(captured).toBe("/api/v1/jobs/weird%20id");
    expect(info.status).toBe("completed");
  });
});

describe("pollJob", () => {
  it("returns the first terminal status it sees", async () => {
    const sequence = ["pending", "processing", "processing", "completed"] as const;
    let i = 0;
    mockFetch(async () => {
      const status = sequence[Math.min(i++, sequence.length - 1)];
      return new Response(
        JSON.stringify({
          job_id: "j",
          status,
          result_url: status === "completed" ? "/files/j.glb" : null,
          error: null,
        }),
        { status: 200 },
      );
    });
    const onUpdate = vi.fn();
    const info = await pollJob("j", { intervalMs: 0, onUpdate });
    expect(info.status).toBe("completed");
    expect(info.result_url).toBe("/files/j.glb");
    expect(onUpdate).toHaveBeenCalledTimes(4);
  });

  it("aborts cleanly when the signal fires", async () => {
    mockFetch(
      async () =>
        new Response(
          JSON.stringify({ job_id: "j", status: "processing", result_url: null, error: null }),
          { status: 200 },
        ),
    );
    const controller = new AbortController();
    const promise = pollJob("j", { intervalMs: 50, signal: controller.signal });
    setTimeout(() => controller.abort(), 10);
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });
});
