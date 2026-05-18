// ─── Generation Parameters ────────────────────────────────────────────────────
// Mirrors backend app/schemas.py GenerationParams

export interface GenerationParams {
  // Shape & layout
  shape: string
  generation_mode: string
  trailName: string
  objSize: number
  shapeRotation: number
  rectangleHeight: number
  ellipseRatio: number

  // Elevation API
  api: string
  dataset: string
  openTopographyDataset: string
  scaleElevation: number
  fixedElevationScale: boolean
  scalemode: string
  scaleLat1: number
  scaleLon1: number
  scaleLat2: number
  scaleLon2: number

  // Mesh quality
  num_subdivisions: number
  minThickness: number
  pathThickness: number
  pathScale: number
  overwritePathElevation: boolean

  // Color / element mode
  singleColorMode: boolean
  tolerance: number
  toleranceElements: number
  elementMode: string
  elementModeInset: number

  // Water layers
  col_wPondsActive: boolean
  col_wSmallRiversActive: boolean
  col_wBigRiversActive: boolean
  col_wStreamWidth: number
  col_wArea: number

  // Land cover layers
  col_fActive: boolean
  col_fArea: number
  col_cActive: boolean
  col_cArea: number
  col_grActive: boolean
  col_grArea: number
  col_faActive: boolean
  col_faArea: number
  col_glActive: boolean
  col_glArea: number
  col_scrActive: boolean
  col_scrArea: number
  col_KeepManifold: boolean

  // 3-D elements
  el_bActive: boolean
  el_bHeightMultiplier: number
  el_sBigActive: boolean
  el_sMedActive: boolean
  el_sSmallActive: boolean
  el_sMultiplier: number
  el_oActive: boolean
  el_oFlip: boolean

  // Terrain offsets
  xTerrainOffset: number
  yTerrainOffset: number

  // Cache
  disableCache: boolean
  ccacheSize: number
  selfHosted: string
  apiRetries: number

  // Text / labels
  titlefield: string
  textfield1: string
  textfield2: string
  textfield3: string
  textFont: string
  textSize: number
  textSizeTitle: number
  titleIcon: string
  iconText1: string
  iconText2: string
  iconText3: string

  // Plate / border
  outerBorderSize: number
  plateThickness: number
  plateInsertValue: number
  plateBevel: number

  // Terrain / map mode coordinates
  jMapLat: number
  jMapLon: number
  jMapRadius: number
  jMapLat1: number
  jMapLon1: number
  jMapLat2: number
  jMapLon2: number

  // Magnets
  magnetHeight: number
  magnetDiameter: number

  // Contour lines / mountains
  mountain_treshold: number
  cl_thickness: number
  cl_distance: number
  cl_offset: number

  // Export
  disable_auto_export: boolean
  disable_3mf_export: boolean
  exportformat: string
}

// ─── Job Status ───────────────────────────────────────────────────────────────

export interface JobStatus {
  job_id: string
  status: 'pending' | 'running' | 'done' | 'failed'
  progress: number  // 0.0 – 1.0
  phase: string
  message: string
  files: string[]
  error: string | null
  created_at: number  // unix timestamp
}

// ─── App State Machine ────────────────────────────────────────────────────────

export type AppState =
  | 'idle'
  | 'uploading'
  | 'uploaded'
  | 'generating'
  | 'done'
  | 'error'

// ─── Upload Response ──────────────────────────────────────────────────────────

export interface UploadResponse {
  upload_id: string
  filename: string
}

// ─── Job Submit Response ──────────────────────────────────────────────────────

export interface JobSubmitResponse {
  job_id: string
}

// ─── SSE Progress Event ───────────────────────────────────────────────────────

export interface SSEProgressEvent {
  event: 'progress' | 'complete' | 'error'
  progress?: number
  phase?: string
  message?: string
  files?: string[]
  error?: string
}
