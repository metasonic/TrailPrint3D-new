import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AppStateProvider } from "@/state/AppState";
import { UploadForm } from "@/components/UploadForm";

function renderForm(onUpload?: (f: File) => void) {
  return render(
    <AppStateProvider>
      <UploadForm onUpload={onUpload} />
    </AppStateProvider>,
  );
}

describe("UploadForm", () => {
  it("prompts the user to drop or choose a file", () => {
    renderForm();
    expect(screen.getByText(/Drop a \.gpx file/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /choose file/i })).toBeInTheDocument();
  });

  it("invokes onUpload when a .gpx file is selected", () => {
    const onUpload = vi.fn();
    renderForm(onUpload);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["<gpx/>"], "track.gpx", { type: "application/gpx+xml" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("rejects non-gpx files with an alert", () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const onUpload = vi.fn();
    renderForm(onUpload);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["not gpx"], "track.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(alertSpy).toHaveBeenCalled();
    expect(onUpload).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });
});
