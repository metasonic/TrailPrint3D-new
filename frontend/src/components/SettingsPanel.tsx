import { useState, useCallback } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Hexagon,
  Circle,
  Square,
  Triangle,
} from 'lucide-react'
import type { GenerationParams } from '../types'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SettingsPanelProps {
  params: Partial<GenerationParams>
  onChange: (key: keyof GenerationParams, value: GenerationParams[keyof GenerationParams]) => void
  disabled?: boolean
}

// ── Defaults (mirrors backend) ─────────────────────────────────────────────────

export const DEFAULT_PARAMS: GenerationParams = {
  shape: 'HEXAGON',
  generation_mode: 'GENERATION',
  trailName: '',
  objSize: 100,
  shapeRotation: 0,
  rectangleHeight: 100,
  ellipseRatio: 0.75,
  api: 'TERRAIN-TILES',
  dataset: 'aster30m',
  openTopographyDataset: 'SRTMGL1',
  scaleElevation: 1.0,
  fixedElevationScale: false,
  scalemode: 'FACTOR',
  scaleLat1: 0,
  scaleLon1: 0,
  scaleLat2: 0,
  scaleLon2: 0,
  num_subdivisions: 4,
  minThickness: 2.0,
  pathThickness: 1.2,
  pathScale: 0.8,
  overwritePathElevation: true,
  singleColorMode: false,
  tolerance: 0.2,
  toleranceElements: 0.4,
  elementMode: 'PAINT',
  elementModeInset: 2.0,
  col_wPondsActive: false,
  col_wSmallRiversActive: false,
  col_wBigRiversActive: false,
  col_wStreamWidth: 1.0,
  col_wArea: 1.0,
  col_fActive: false,
  col_fArea: 10.0,
  col_cActive: false,
  col_cArea: 1.0,
  col_grActive: false,
  col_grArea: 1.0,
  col_faActive: false,
  col_faArea: 1.0,
  col_glActive: false,
  col_glArea: 1.0,
  col_scrActive: false,
  col_scrArea: 1.0,
  col_KeepManifold: false,
  el_bActive: false,
  el_bHeightMultiplier: 1.0,
  el_sBigActive: false,
  el_sMedActive: false,
  el_sSmallActive: false,
  el_sMultiplier: 1.0,
  el_oActive: false,
  el_oFlip: false,
  xTerrainOffset: 0,
  yTerrainOffset: 0,
  disableCache: false,
  ccacheSize: 50000,
  selfHosted: '',
  apiRetries: 5,
  titlefield: '{name}',
  textfield1: '{length}',
  textfield2: '{elevation}',
  textfield3: '{duration}',
  textFont: '',
  textSize: 5,
  textSizeTitle: 0,
  titleIcon: 'no',
  iconText1: 'distance',
  iconText2: 'elevation',
  iconText3: 'time',
  outerBorderSize: 20,
  plateThickness: 5.0,
  plateInsertValue: 0.0,
  plateBevel: 0.0,
  jMapLat: 49.0,
  jMapLon: 9.0,
  jMapRadius: 50.0,
  jMapLat1: 48.0,
  jMapLon1: 8.0,
  jMapLat2: 49.0,
  jMapLon2: 9.0,
  magnetHeight: 2.5,
  magnetDiameter: 6.3,
  mountain_treshold: 60,
  cl_thickness: 0.2,
  cl_distance: 2.0,
  cl_offset: 0.0,
  disable_auto_export: false,
  disable_3mf_export: false,
  exportformat: 'AUTO',
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface SectionProps {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}

function Section({ title, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <button
        type="button"
        className="section-header px-4"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span>{title}</span>
        {open
          ? <ChevronDown size={16} className="text-gray-500" />
          : <ChevronRight size={16} className="text-gray-500" />}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-4 border-t border-gray-800 bg-gray-900/50">
          {children}
        </div>
      )}
    </div>
  )
}

interface ToggleProps {
  checked: boolean
  onChange: (val: boolean) => void
  label: string
  disabled?: boolean
  hint?: string
}

function Toggle({ checked, onChange, label, disabled, hint }: ToggleProps) {
  return (
    <div className="flex items-start gap-3 cursor-pointer group">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={[
          'toggle mt-0.5 shrink-0',
          checked ? 'bg-orange-500' : 'bg-gray-700',
          disabled ? 'opacity-50 cursor-not-allowed' : '',
        ].join(' ')}
      >
        <span
          className={[
            'toggle-thumb',
            checked ? 'translate-x-4' : 'translate-x-1',
          ].join(' ')}
        />
      </button>
      <div>
        <span className="text-sm text-gray-300 group-hover:text-white transition-colors">
          {label}
        </span>
        {hint && <p className="text-xs text-gray-600 mt-0.5">{hint}</p>}
      </div>
    </div>
  )
}

interface SliderRowProps {
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (val: number) => void
  disabled?: boolean
  unit?: string
  hint?: string
}

function SliderRow({ label, value, min, max, step = 1, onChange, disabled, unit, hint }: SliderRowProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm text-gray-400">{label}</label>
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={value}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
            aria-label={label}
            onChange={e => onChange(parseFloat(e.target.value) || min)}
            className="w-20 text-right bg-gray-800 border border-gray-700 rounded px-2 py-0.5
                       text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-orange-500
                       disabled:opacity-50"
          />
          {unit && <span className="text-xs text-gray-600">{unit}</span>}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-label={label}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full disabled:opacity-50"
      />
      {hint && <p className="text-xs text-gray-600 mt-0.5">{hint}</p>}
    </div>
  )
}

// ── Shape Selector ────────────────────────────────────────────────────────────

const SHAPES = [
  { value: 'HEXAGON', label: 'Hex', icon: <Hexagon size={18} /> },
  { value: 'CIRCLE', label: 'Circle', icon: <Circle size={18} /> },
  { value: 'SQUARE', label: 'Square', icon: <Square size={18} /> },
  { value: 'RECTANGLE', label: 'Rect', icon: <Square size={18} strokeWidth={1} /> },
  { value: 'TRIANGLE', label: 'Tri', icon: <Triangle size={18} /> },
  { value: 'ROUND_RECTANGLE', label: 'Rnd Rect', icon: <Square size={18} strokeWidth={3} style={{ borderRadius: 4 }} /> },
  { value: 'DIAMOND', label: 'Diamond', icon: <Square size={18} style={{ transform: 'rotate(45deg)' }} /> },
  {
    value: 'SPADE_FRAME', label: 'Spade',
    icon: <span className="text-base leading-none select-none">♠</span>,
  },
  {
    value: 'HEART_FRAME', label: 'Heart',
    icon: <span className="text-base leading-none select-none">♥</span>,
  },
  {
    value: 'STAR', label: 'Star',
    icon: <span className="text-base leading-none select-none">★</span>,
  },
]

const TEXT_SHAPES = ['HEXAGON_TEXT', 'SQUARE_TEXT', 'RECTANGLE_TEXT', 'CIRCLE_TEXT']
const ALL_SHAPE_OPTIONS = [
  ...SHAPES,
  { value: 'HEXAGON_TEXT', label: 'Hex+Text', icon: <Hexagon size={18} /> },
  { value: 'SQUARE_TEXT', label: 'Sq+Text', icon: <Square size={18} /> },
  { value: 'RECTANGLE_TEXT', label: 'Rect+Text', icon: <Square size={18} strokeWidth={1} /> },
  { value: 'CIRCLE_TEXT', label: 'Circ+Text', icon: <Circle size={18} /> },
]

// ── Main Component ────────────────────────────────────────────────────────────

export default function SettingsPanel({ params, onChange, disabled = false }: SettingsPanelProps) {
  const get = useCallback(
    <K extends keyof GenerationParams>(key: K): GenerationParams[K] =>
      (params[key] as GenerationParams[K]) ?? DEFAULT_PARAMS[key],
    [params],
  )

  const shape = get('shape')
  const hasTextPlate = TEXT_SHAPES.includes(shape)

  return (
    <div className="space-y-3">
      {/* ── Basic ──────────────────────────────────────────────────────────── */}
      <Section title="Basic" defaultOpen>
        {/* Shape selector */}
        <div>
          <label className="label">Shape</label>
          <div role="group" aria-label="Shape" className="flex flex-wrap gap-2">
            {ALL_SHAPE_OPTIONS.map(opt => (
              <button
                key={opt.value}
                type="button"
                disabled={disabled}
                aria-pressed={shape === opt.value}
                onClick={() => onChange('shape', opt.value)}
                className={[
                  'flex flex-col items-center gap-1 px-3 py-2 rounded-lg border text-xs',
                  'transition-all duration-150 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed',
                  shape === opt.value
                    ? 'border-orange-500 bg-orange-500/10 text-orange-300'
                    : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500 hover:text-gray-200',
                ].join(' ')}
                title={opt.value}
              >
                {opt.icon}
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Trail name */}
        <div>
          <label className="label" htmlFor="trailName">Trail Name</label>
          <input
            id="trailName"
            type="text"
            value={get('trailName')}
            disabled={disabled}
            onChange={e => onChange('trailName', e.target.value)}
            placeholder="Auto-detected from GPX"
            className="input-field disabled:opacity-50"
          />
        </div>

        {/* Map size */}
        <SliderRow
          label="Map Size"
          value={get('objSize')}
          min={5}
          max={500}
          step={5}
          unit="mm"
          disabled={disabled}
          onChange={val => onChange('objSize', val)}
          hint="Final bounding box diameter of the printed model"
        />

        {/* Shape rotation */}
        <SliderRow
          label="Shape Rotation"
          value={get('shapeRotation')}
          min={-360}
          max={360}
          step={1}
          unit="°"
          disabled={disabled}
          onChange={val => onChange('shapeRotation', val)}
        />

        {shape === 'RECTANGLE' || shape === 'RECTANGLE_TEXT' ? (
          <SliderRow
            label="Rectangle Height"
            value={get('rectangleHeight')}
            min={5}
            max={500}
            step={5}
            unit="mm"
            disabled={disabled}
            onChange={val => onChange('rectangleHeight', val)}
          />
        ) : null}
      </Section>

      {/* ── Elevation ──────────────────────────────────────────────────────── */}
      <Section title="Elevation">
        <div>
          <label className="label">Elevation API</label>
          <div className="space-y-2">
            {[
              { value: 'TERRAIN-TILES', label: 'Terrain Tiles', hint: 'Fast · Mapzen/AWS hosted' },
              { value: 'OPENTOPODATA', label: 'Opentopodata', hint: 'Open dataset API' },
              { value: 'OPEN-ELEVATION', label: 'Open Elevation', hint: 'Community API' },
              { value: 'OPENTOPOGRAPHY', label: 'OpenTopography', hint: 'Requires API key' },
            ].map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-3 cursor-pointer group p-2 rounded-lg hover:bg-gray-800 transition-colors"
              >
                <input
                  type="radio"
                  name="api"
                  value={opt.value}
                  checked={get('api') === opt.value}
                  disabled={disabled}
                  onChange={() => onChange('api', opt.value)}
                  className="accent-orange-500 disabled:opacity-50"
                />
                <div>
                  <p className="text-sm text-gray-300 group-hover:text-white transition-colors">
                    {opt.label}
                  </p>
                  <p className="text-xs text-gray-600">{opt.hint}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {get('api') === 'OPENTOPODATA' && (
          <div>
            <label className="label" htmlFor="dataset">Dataset</label>
            <select
              id="dataset"
              value={get('dataset')}
              disabled={disabled}
              onChange={e => onChange('dataset', e.target.value)}
              className="input-field disabled:opacity-50"
            >
              {['aster30m', 'eudem25m', 'mapzen', 'ned10m', 'nzdem8m', 'srtm90m', 'emod2018'].map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
        )}

        {get('api') === 'OPENTOPOGRAPHY' && (
          <div>
            <label className="label" htmlFor="openTopographyDataset">OpenTopography Dataset</label>
            <select
              id="openTopographyDataset"
              value={get('openTopographyDataset')}
              disabled={disabled}
              onChange={e => onChange('openTopographyDataset', e.target.value)}
              className="input-field disabled:opacity-50"
            >
              {['SRTMGL1', 'SRTMGL3', 'AW3D30', 'COP30', 'NASADEM'].map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
        )}

        <SliderRow
          label="Elevation Scale"
          value={get('scaleElevation')}
          min={0.1}
          max={10}
          step={0.1}
          disabled={disabled}
          onChange={val => onChange('scaleElevation', val)}
          hint="Vertical exaggeration multiplier"
        />

        <Toggle
          checked={get('fixedElevationScale')}
          onChange={val => onChange('fixedElevationScale', val)}
          label="Fixed Elevation Scale (10 mm span)"
          disabled={disabled}
          hint="Forces the elevation range to always span 10 mm regardless of terrain"
        />

        <SliderRow
          label="Subdivisions / Resolution"
          value={get('num_subdivisions')}
          min={1}
          max={10}
          step={1}
          disabled={disabled}
          onChange={val => onChange('num_subdivisions', val)}
          hint="Higher = more mesh detail, slower generation"
        />
      </Section>

      {/* ── Elements ───────────────────────────────────────────────────────── */}
      <Section title="Map Elements">
        <p className="text-xs text-gray-600 -mt-1">
          Elements are fetched from OpenStreetMap. Enable only what you need.
        </p>

        {/* Water */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Water</p>
          <Toggle
            checked={get('col_wPondsActive')}
            onChange={val => onChange('col_wPondsActive', val)}
            label="Ponds &amp; Lakes"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_wSmallRiversActive')}
            onChange={val => onChange('col_wSmallRiversActive', val)}
            label="Small Rivers / Streams"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_wBigRiversActive')}
            onChange={val => onChange('col_wBigRiversActive', val)}
            label="Big Rivers"
            disabled={disabled}
          />
          {(get('col_wSmallRiversActive') || get('col_wBigRiversActive')) && (
            <SliderRow
              label="Stream Width"
              value={get('col_wStreamWidth')}
              min={0.1}
              max={5}
              step={0.1}
              unit="×"
              disabled={disabled}
              onChange={val => onChange('col_wStreamWidth', val)}
            />
          )}
        </div>

        {/* Land cover */}
        <div className="space-y-2 border-t border-gray-800 pt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Land Cover</p>
          <Toggle
            checked={get('col_fActive')}
            onChange={val => onChange('col_fActive', val)}
            label="Forests"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_grActive')}
            onChange={val => onChange('col_grActive', val)}
            label="Greenspaces / Parks"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_faActive')}
            onChange={val => onChange('col_faActive', val)}
            label="Farmland"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_glActive')}
            onChange={val => onChange('col_glActive', val)}
            label="Glaciers"
            disabled={disabled}
          />
          <Toggle
            checked={get('col_scrActive')}
            onChange={val => onChange('col_scrActive', val)}
            label="Scree / Rock"
            disabled={disabled}
          />
          <Toggle
            checked={get('el_oActive')}
            onChange={val => onChange('el_oActive', val)}
            label="Ocean"
            disabled={disabled}
          />
        </div>

        {/* Buildings */}
        <div className="space-y-2 border-t border-gray-800 pt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Buildings</p>
          <Toggle
            checked={get('el_bActive')}
            onChange={val => onChange('el_bActive', val)}
            label="Buildings"
            disabled={disabled}
          />
          {get('el_bActive') && (
            <SliderRow
              label="Building Height Multiplier"
              value={get('el_bHeightMultiplier')}
              min={0.1}
              max={5}
              step={0.1}
              unit="×"
              disabled={disabled}
              onChange={val => onChange('el_bHeightMultiplier', val)}
            />
          )}
        </div>

        {/* Roads */}
        <div className="space-y-2 border-t border-gray-800 pt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Roads</p>
          <Toggle
            checked={get('el_sBigActive')}
            onChange={val => onChange('el_sBigActive', val)}
            label="Major Roads"
            disabled={disabled}
          />
          <Toggle
            checked={get('el_sMedActive')}
            onChange={val => onChange('el_sMedActive', val)}
            label="Secondary Roads"
            disabled={disabled}
          />
          <Toggle
            checked={get('el_sSmallActive')}
            onChange={val => onChange('el_sSmallActive', val)}
            label="Minor Roads / Paths"
            disabled={disabled}
          />
          {(get('el_sBigActive') || get('el_sMedActive') || get('el_sSmallActive')) && (
            <SliderRow
              label="Road Width Multiplier"
              value={get('el_sMultiplier')}
              min={0.1}
              max={5}
              step={0.1}
              unit="×"
              disabled={disabled}
              onChange={val => onChange('el_sMultiplier', val)}
            />
          )}
        </div>

        {/* City boundaries */}
        <div className="border-t border-gray-800 pt-4">
        <Toggle
          checked={get('col_cActive')}
          onChange={val => onChange('col_cActive', val)}
          label="City / Admin Boundaries"
          disabled={disabled}
        />
        <Toggle
          checked={get('col_KeepManifold')}
          onChange={val => onChange('col_KeepManifold', val)}
          label="Keep Manifold (auto-repair mesh)"
          disabled={disabled}
        />
        </div>
      </Section>

      {/* ── Trail ──────────────────────────────────────────────────────────── */}
      <Section title="Trail">
        <SliderRow
          label="Path Thickness"
          value={get('pathThickness')}
          min={0.1}
          max={5}
          step={0.1}
          unit="mm"
          disabled={disabled}
          onChange={val => onChange('pathThickness', val)}
        />

        <SliderRow
          label="Path Scale"
          value={get('pathScale')}
          min={0.1}
          max={3}
          step={0.05}
          unit="×"
          disabled={disabled}
          onChange={val => onChange('pathScale', val)}
        />

        <Toggle
          checked={get('overwritePathElevation')}
          onChange={val => onChange('overwritePathElevation', val)}
          label="Overwrite Path Elevation"
          disabled={disabled}
          hint="Path always appears on top of terrain surface"
        />

        <Toggle
          checked={get('singleColorMode')}
          onChange={val => onChange('singleColorMode', val)}
          label="Single Color Mode"
          disabled={disabled}
          hint="Disables per-element coloring for single-filament prints"
        />
      </Section>

      {/* ── Text & Plate ───────────────────────────────────────────────────── */}
      {hasTextPlate && (
        <Section title="Text &amp; Plate">
          <p className="text-xs text-gray-500 bg-gray-800 rounded-lg px-3 py-2 leading-relaxed">
            Template codes: <code className="text-orange-400">{'{name}'}</code> trail name,{' '}
            <code className="text-orange-400">{'{length}'}</code> distance,{' '}
            <code className="text-orange-400">{'{elevation}'}</code> elevation gain,{' '}
            <code className="text-orange-400">{'{duration}'}</code> time
          </p>

          <div>
            <label className="label" htmlFor="titlefield">Title</label>
            <input
              id="titlefield"
              type="text"
              value={get('titlefield')}
              disabled={disabled}
              onChange={e => onChange('titlefield', e.target.value)}
              className="input-field disabled:opacity-50"
              placeholder="{name}"
            />
          </div>

          {(['textfield1', 'textfield2', 'textfield3'] as const).map((field, i) => (
            <div key={field}>
              <label className="label" htmlFor={field}>Text Line {i + 1}</label>
              <input
                id={field}
                type="text"
                value={get(field)}
                disabled={disabled}
                onChange={e => onChange(field, e.target.value)}
                className="input-field disabled:opacity-50"
              />
            </div>
          ))}

          <div>
            <label className="label" htmlFor="titleIcon">Title Icon</label>
            <select
              id="titleIcon"
              value={get('titleIcon')}
              disabled={disabled}
              onChange={e => onChange('titleIcon', e.target.value)}
              className="input-field disabled:opacity-50"
            >
              {['no', 'hiking', 'cycling', 'running', 'skiing', 'swimming'].map(v => (
                <option key={v} value={v}>{v === 'no' ? 'None' : v.charAt(0).toUpperCase() + v.slice(1)}</option>
              ))}
            </select>
          </div>

          <SliderRow
            label="Plate Thickness"
            value={get('plateThickness')}
            min={1}
            max={20}
            step={0.5}
            unit="mm"
            disabled={disabled}
            onChange={val => onChange('plateThickness', val)}
          />

          <SliderRow
            label="Plate Bevel"
            value={get('plateBevel')}
            min={0}
            max={5}
            step={0.1}
            unit="mm"
            disabled={disabled}
            onChange={val => onChange('plateBevel', val)}
          />

          <SliderRow
            label="Outer Border Size"
            value={get('outerBorderSize')}
            min={0}
            max={50}
            step={1}
            unit="mm"
            disabled={disabled}
            onChange={val => onChange('outerBorderSize', val)}
          />
        </Section>
      )}

      {/* ── Advanced ───────────────────────────────────────────────────────── */}
      <Section title="Advanced">
        <SliderRow
          label="Min Thickness"
          value={get('minThickness')}
          min={0.5}
          max={10}
          step={0.1}
          unit="mm"
          disabled={disabled}
          onChange={val => onChange('minThickness', val)}
          hint="Minimum base thickness of the 3D model"
        />

        <SliderRow
          label="Terrain Offset X"
          value={get('xTerrainOffset')}
          min={-50}
          max={50}
          step={0.1}
          unit="km"
          disabled={disabled}
          onChange={val => onChange('xTerrainOffset', val)}
        />

        <SliderRow
          label="Terrain Offset Y"
          value={get('yTerrainOffset')}
          min={-50}
          max={50}
          step={0.1}
          unit="km"
          disabled={disabled}
          onChange={val => onChange('yTerrainOffset', val)}
        />

        <div>
          <label className="label" htmlFor="elementMode">Element Mode</label>
          <select
            id="elementMode"
            value={get('elementMode')}
            disabled={disabled}
            onChange={e => onChange('elementMode', e.target.value)}
            className="input-field disabled:opacity-50"
          >
            <option value="PAINT">Paint (color only)</option>
            <option value="INSET">Inset (recessed)</option>
            <option value="EMBOSS">Emboss (raised)</option>
          </select>
        </div>

        {get('elementMode') === 'INSET' && (
          <SliderRow
            label="Element Inset Depth"
            value={get('elementModeInset')}
            min={0.1}
            max={10}
            step={0.1}
            unit="mm"
            disabled={disabled}
            onChange={val => onChange('elementModeInset', val)}
          />
        )}

        <div>
          <label className="label" htmlFor="exportformat">Export Format</label>
          <select
            id="exportformat"
            value={get('exportformat')}
            disabled={disabled}
            onChange={e => onChange('exportformat', e.target.value)}
            className="input-field disabled:opacity-50"
          >
            <option value="AUTO">Auto (all supported)</option>
            <option value="STL">STL only</option>
            <option value="OBJ">OBJ only</option>
            <option value="3MF">3MF only</option>
          </select>
        </div>

        <Toggle
          checked={get('disableCache')}
          onChange={val => onChange('disableCache', val)}
          label="Disable Cache"
          disabled={disabled}
          hint="Forces fresh elevation data download — slower but always current"
        />

        <SliderRow
          label="API Retries"
          value={get('apiRetries')}
          min={1}
          max={20}
          step={1}
          disabled={disabled}
          onChange={val => onChange('apiRetries', val)}
          hint="Number of retries on network error when fetching elevation data"
        />

        <Toggle
          checked={get('disable_3mf_export')}
          onChange={val => onChange('disable_3mf_export', val)}
          label="Disable 3MF Export"
          disabled={disabled}
        />
      </Section>
    </div>
  )
}
