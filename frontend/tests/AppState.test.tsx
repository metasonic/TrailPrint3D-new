import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { AppStateProvider, useAppState } from "@/state/AppState";
import { DEFAULT_SETTINGS } from "@/types/settings";

function wrap({ children }: { children: React.ReactNode }) {
  return <AppStateProvider>{children}</AppStateProvider>;
}

describe("AppState", () => {
  it("initialises with the Phase 2 default settings", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
    expect(result.current.gpx).toBeNull();
    expect(result.current.previewUrl).toBeNull();
    expect(result.current.jobStatus).toBeNull();
  });

  it("updates a single setting without resetting the others", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.setSetting("shape", "square"));
    expect(result.current.settings.shape).toBe("square");
    expect(result.current.settings.terrain_scale).toBe(DEFAULT_SETTINGS.terrain_scale);
  });
});
