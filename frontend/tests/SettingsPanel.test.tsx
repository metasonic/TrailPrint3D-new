import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AppStateProvider } from "@/state/AppState";
import { SettingsPanel } from "@/components/SettingsPanel";

function renderPanel() {
  return render(
    <AppStateProvider>
      <SettingsPanel />
    </AppStateProvider>,
  );
}

describe("SettingsPanel", () => {
  it("renders the three shape radios with hexagon selected by default", () => {
    renderPanel();
    expect(screen.getByLabelText(/square/i)).not.toBeChecked();
    expect(screen.getByLabelText(/circle/i)).not.toBeChecked();
    expect(screen.getByLabelText(/hexagon/i)).toBeChecked();
  });

  it("updates terrain scale via slider", () => {
    renderPanel();
    const slider = screen.getByLabelText(/terrain scale/i) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "2.5" } });
    expect(slider.value).toBe("2.5");
  });

  it("uses the locked Phase 2 defaults", () => {
    renderPanel();
    expect(screen.getByLabelText(/frame thickness/i)).toHaveValue(5);
    expect(screen.getByLabelText(/bbox padding/i)).toHaveValue("10");
    expect(screen.getByLabelText(/track thickness/i)).toHaveValue("1.2");
  });
});
