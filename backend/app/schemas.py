from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class GenerationParams(BaseModel):
    # Shape & layout
    shape: str = "HEXAGON"
    generation_mode: str = "GENERATION"
    trailName: str = ""
    objSize: int = Field(default=100, ge=5, le=10000)
    shapeRotation: int = Field(default=0, ge=-360, le=360)
    rectangleHeight: int = 100
    ellipseRatio: float = 0.75

    # Elevation API
    api: str = "TERRAIN-TILES"
    dataset: str = "aster30m"
    openTopographyDataset: str = "SRTMGL1"
    scaleElevation: float = Field(default=1.0, ge=0.0, le=10000.0)
    fixedElevationScale: bool = False
    scalemode: str = "FACTOR"
    scaleLat1: float = 0.0
    scaleLon1: float = 0.0
    scaleLat2: float = 0.0
    scaleLon2: float = 0.0

    # Mesh quality
    num_subdivisions: int = Field(default=4, ge=1, le=10)
    minThickness: float = Field(default=2.0, ge=0.5, le=1000.0)
    pathThickness: float = Field(default=1.2, ge=0.1, le=5.0)
    pathScale: float = 0.8
    overwritePathElevation: bool = True

    # Color / element mode
    singleColorMode: bool = False
    tolerance: float = 0.2
    toleranceElements: float = 0.4
    elementMode: str = "PAINT"
    elementModeInset: float = 2.0

    # Water layers
    col_wPondsActive: bool = False
    col_wSmallRiversActive: bool = False
    col_wBigRiversActive: bool = False
    col_wStreamWidth: float = 1.0
    col_wArea: float = 1.0

    # Land cover layers
    col_fActive: bool = False
    col_fArea: float = 10.0
    col_cActive: bool = False
    col_cArea: float = 1.0
    col_grActive: bool = False
    col_grArea: float = 1.0
    col_faActive: bool = False
    col_faArea: float = 1.0
    col_glActive: bool = False
    col_glArea: float = 1.0
    col_scrActive: bool = False
    col_scrArea: float = 1.0
    col_KeepManifold: bool = False

    # 3-D elements
    el_bActive: bool = False
    el_bHeightMultiplier: float = 1.0
    el_sBigActive: bool = False
    el_sMedActive: bool = False
    el_sSmallActive: bool = False
    el_sMultiplier: float = 1.0
    el_oActive: bool = False
    el_oFlip: bool = False

    # Terrain offsets
    xTerrainOffset: float = 0.0
    yTerrainOffset: float = 0.0

    # Cache
    disableCache: bool = False
    ccacheSize: int = 50000
    selfHosted: str = ""
    apiRetries: int = 5

    # Text / labels
    titlefield: str = "{name}"
    textfield1: str = "{length}"
    textfield2: str = "{elevation}"
    textfield3: str = "{duration}"
    textFont: str = ""
    textSize: int = 5
    textSizeTitle: int = 0
    titleIcon: str = "no"
    iconText1: str = "distance"
    iconText2: str = "elevation"
    iconText3: str = "time"

    # Plate / border
    outerBorderSize: int = 20
    plateThickness: float = 5.0
    plateInsertValue: float = 0.0
    plateBevel: float = 0.0

    # Terrain / map mode coordinates
    jMapLat: float = 49.0
    jMapLon: float = 9.0
    jMapRadius: float = 50.0
    jMapLat1: float = 48.0
    jMapLon1: float = 8.0
    jMapLat2: float = 49.0
    jMapLon2: float = 9.0

    # Magnets
    magnetHeight: float = 2.5
    magnetDiameter: float = 6.3

    # Contour lines / mountains
    mountain_treshold: int = 60
    cl_thickness: float = 0.2
    cl_distance: float = 2.0
    cl_offset: float = 0.0

    # Export
    disable_auto_export: bool = False
    disable_3mf_export: bool = False
    exportformat: str = "AUTO"


class JobSubmitRequest(BaseModel):
    upload_id: str
    params: GenerationParams = Field(default_factory=GenerationParams)


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending | running | done | failed
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    phase: str = ""
    message: str = ""
    files: List[str] = []
    error: Optional[str] = None
    created_at: float  # unix timestamp
