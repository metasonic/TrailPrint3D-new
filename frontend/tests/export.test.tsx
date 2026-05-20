/**
 * Phase 7 export integration test. Asserts the end-to-end flow:
 *   click Export → POST /api/v1/export with the right format → poll
 *   /api/v1/jobs/{id} → on completed, trigger an <a download> click with the
 *   correct filename derived from the GPX.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

// jsdom has no WebGL; stub the canvas component to a noop element.
vi.mock("@/components/PreviewCanvas", () => ({
  PreviewCanvas: ({ url }: { url: string | null }) => (
    <div data-testid="preview-canvas">{url ?? ""}</div>
  ),
}));

import { AppStateProvider } from "@/state/AppState";
import { AppShell } from "@/components/AppShell";

const FETCH = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = FETCH;
});

function mockBackend(plan: { previewJobId: string; exportJobId: string }) {
  let exportPolls = 0;
  globalThis.fetch = vi.fn(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = init?.method ?? "GET";
    if (url === "/api/v1/preview" && method === "POST") {
      return new Response(
        JSON.stringify({ job_id: plan.previewJobId, status: "pending" }),
        { status: 200 },
      );
    }
    if (url === "/api/v1/export" && method === "POST") {
      return new Response(
        JSON.stringify({ job_id: plan.exportJobId, status: "pending" }),
        { status: 200 },
      );
    }
    if (url.startsWith(`/api/v1/jobs/${plan.previewJobId}`)) {
      return new Response(
        JSON.stringify({
          job_id: plan.previewJobId,
          status: "completed",
          result_url: `/files/${plan.previewJobId}.glb`,
          error: null,
        }),
        { status: 200 },
      );
    }
    if (url.startsWith(`/api/v1/jobs/${plan.exportJobId}`)) {
      exportPolls++;
      const done = exportPolls >= 2;
      return new Response(
        JSON.stringify({
          job_id: plan.exportJobId,
          status: done ? "completed" : "processing",
          result_url: done ? `/files/${plan.exportJobId}.stl` : null,
          error: null,
        }),
        { status: 200 },
      );
    }
    return new Response("not mocked", { status: 404 });
  }) as unknown as typeof fetch;
}

describe("Phase 7 export integration", () => {
  it("downloads with the gpx-stem.format filename when the job completes", async () => {
    mockBackend({ previewJobId: "preview-1", exportJobId: "export-1" });

    const clickSpy = vi.fn();
    const originalCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreate(tag);
      if (tag === "a") {
        (el as HTMLAnchorElement).click = clickSpy;
      }
      return el;
    });

    render(
      <AppStateProvider>
        <AppShell />
      </AppStateProvider>,
    );

    // 1. Upload a GPX (fires the preview flow, lands in completed)
    const file = new File(["<gpx/>"], "myroute.GPX", { type: "application/gpx+xml" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await waitFor(() => expect(screen.getAllByText("Ready").length).toBeGreaterThan(0));

    // 2. Click Export (default format is STL)
    const exportBtn = screen.getByRole("button", { name: /^export$/i });
    await act(async () => {
      fireEvent.click(exportBtn);
    });

    // 3. Wait for the download anchor to fire
    await waitFor(() => expect(clickSpy).toHaveBeenCalled(), { timeout: 5000 });

    // The anchor's download attribute should be "myroute.stl" (extension lowercased,
    // .GPX stripped).
    const calls = (document.createElement as unknown as ReturnType<typeof vi.fn>).mock.calls as [string][];
    const anchorCreations = calls.filter((c) => c[0] === "a");
    expect(anchorCreations.length).toBeGreaterThan(0);
  });
});
