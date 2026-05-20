/**
 * The brief's five panel-exposed Phase 1 parameters:
 *   shape, terrain_scale, track_thickness_mm, frame_thickness_mm, bbox_padding_percent.
 *
 * Sliders for the three continuous floats; radio for shape; numeric input for
 * frame_thickness_mm. Internal pipeline defaults (model_size_mm, subdivisions)
 * are intentionally not exposed in Phase 1.
 */

import type { Shape } from "@/types/settings";
import { useAppState } from "@/state/AppState";

const SHAPE_OPTIONS: Shape[] = ["square", "circle", "hexagon"];

interface Props {
  onRegenerate?: () => void;
  disabled?: boolean;
}

export function SettingsPanel({ onRegenerate, disabled }: Props) {
  const { settings, setSetting } = useAppState();

  return (
    <div className="flex flex-col gap-5 rounded-(--radius-md) bg-[var(--color-surface)] p-5">
      <header>
        <h2 className="text-base font-semibold">Settings</h2>
        <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
          Five Phase 1 parameters. Defaults follow docs/phase2_pipeline_design.md.
        </p>
      </header>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">
          Shape
        </legend>
        <div className="flex gap-2">
          {SHAPE_OPTIONS.map((s) => (
            <label
              key={s}
              className={[
                "flex-1 cursor-pointer rounded-(--radius-sm) border px-3 py-2 text-center text-sm capitalize transition-colors",
                settings.shape === s
                  ? "border-[var(--color-accent)] bg-[var(--color-surface-raised)] text-[var(--color-ink-primary)]"
                  : "border-[var(--color-edge)] text-[var(--color-ink-muted)] hover:border-[var(--color-accent-strong)]",
              ].join(" ")}
            >
              <input
                type="radio"
                name="shape"
                value={s}
                checked={settings.shape === s}
                onChange={() => setSetting("shape", s)}
                className="sr-only"
              />
              {s}
            </label>
          ))}
        </div>
      </fieldset>

      <Slider
        label="Terrain scale"
        unit="×"
        min={0.1}
        max={5}
        step={0.1}
        value={settings.terrain_scale}
        onChange={(v) => setSetting("terrain_scale", v)}
      />

      <Slider
        label="Track thickness"
        unit="mm"
        min={0.4}
        max={5}
        step={0.1}
        value={settings.track_thickness_mm}
        onChange={(v) => setSetting("track_thickness_mm", v)}
      />

      <Slider
        label="Bbox padding"
        unit="%"
        min={0}
        max={50}
        step={1}
        value={Math.round(settings.bbox_padding_percent * 100)}
        onChange={(v) => setSetting("bbox_padding_percent", v / 100)}
      />

      <label className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">
          Frame thickness (mm)
        </span>
        <input
          type="number"
          min={0.5}
          max={50}
          step={0.5}
          value={settings.frame_thickness_mm}
          onChange={(e) => setSetting("frame_thickness_mm", Number(e.target.value))}
          className="rounded-(--radius-sm) border border-[var(--color-edge)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm text-[var(--color-ink-primary)] focus:border-[var(--color-accent)] focus:outline-none"
        />
      </label>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onRegenerate?.()}
        className="mt-2 inline-flex items-center justify-center rounded-(--radius-sm) bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-[var(--color-canvas)] hover:bg-[var(--color-accent-strong)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        Regenerate preview
      </button>
    </div>
  );
}

function Slider(props: {
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
}) {
  const { label, unit, min, max, step, value, onChange } = props;
  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">
          {label}
        </span>
        <span className="font-mono text-xs text-[var(--color-ink-primary)]">
          {value}
          {unit}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--color-accent)]"
      />
    </label>
  );
}
