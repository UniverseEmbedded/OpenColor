from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# --- 基础协议 ---


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any] = {}


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JobEvent(BaseModel):
    event: str
    job_id: str
    progress: Optional[float] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    result: Optional[Any] = None


# --- 方法特定参数和结果 ---


class HealthPingResult(BaseModel):
    status: str
    version: str
    timestamp: float


class BoardGenerateParams(BaseModel):
    out_dir: Optional[str] = None
    color_system: str = "RYBW"
    n_layers: int = 5
    cell_size_mm: float = 4.0
    layer_height_mm: float = 0.12
    total_cells: int = 26
    data_cells: int = 24

    rows: Optional[int] = None
    cols: Optional[int] = None
    dataRows: Optional[int] = None
    dataCols: Optional[int] = None
    layers: Optional[int] = None
    tileSizeMm: Optional[float] = None
    tile_size_mm: Optional[float] = None
    cellSizeMm: Optional[float] = None
    layerHeightMm: Optional[float] = None
    shrink: Optional[float] = None
    fileName: Optional[str] = None
    file_name: Optional[str] = None
    materials: Optional[List[Dict[str, Any]]] = None
    export_format: str = "3mf"
    export_formats: List[str] = Field(default_factory=lambda: ["3mf"])
    workspace_path: Optional[str] = None
    timestamp: Optional[str] = None


class BoardExportParams(BaseModel):
    spec_path: str
    out_dir: Optional[str] = None
    export_format: str = "3mf"
    export_formats: List[str] = Field(default_factory=lambda: ["3mf"])


class BoardPreviewParams(BaseModel):
    """校准板预览参数"""
    profile_id: str
    spec_path: str
    materials: Optional[List[Dict[str, Any]]] = None
    rows: Optional[int] = None
    cols: Optional[int] = None
    dataRows: Optional[int] = None
    dataCols: Optional[int] = None
    layers: Optional[int] = None
    cell_size_mm: Optional[float] = None
    layer_height_mm: Optional[float] = None
    shrink: Optional[float] = None
    marker_tl: Optional[str] = None
    marker_tr: Optional[str] = None
    marker_br: Optional[str] = None
    marker_bl: Optional[str] = None


class LutExtractParams(BaseModel):
    photo_path: str
    recipes_path: str
    out_dir: Optional[str] = None


class LutDetectParams(BaseModel):
    photo_path: str
    out_dir: Optional[str] = None


class DatasetCreateParams(BaseModel):
    name: str
    out_dir: Optional[str] = None


class DatasetAddObservationParams(BaseModel):
    dataset_path: str
    observation_path: str


class DatasetAggregateParams(BaseModel):
    dataset_path: str
    out_dir: Optional[str] = None


class McrtValidateParams(BaseModel):
    dataset_path: str
    out_dir: Optional[str] = None


class JobManifest(BaseModel):
    """
    任务产物清单（Manifest）
    定义了任务生成的物理产物、材料分配、坐标系等核心信息
    """

    job_id: str
    kind: str
    out_dir: str
    created_at: float

    # 物理产物
    artifacts: Dict[str, Union[str, List[str]]] = Field(default_factory=dict)

    # 打印板相关信息 (如果适用)
    plate_info: Optional[Dict[str, Any]] = None

    # 材料分配 (Slot -> Material ID/Name)
    materials: List[Dict[str, Any]] = Field(default_factory=list)

    # 扩展元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobInfo(BaseModel):
    job_id: str
    out_dir: str


class BitmapExportParams(BaseModel):
    image_path: str
    lut_path: str
    nozzle_width_mm: float = 0.4
    target_width_mm: Optional[float] = None
    n_layers: int = 4
    output_format: str = "stl"
    out_dir: Optional[str] = None


class SvgExportParams(BaseModel):
    svg_path: str
    width_mm: float = 80.0
    thickness_mm: float = 0.8
    tol_mm: float = 0.2
    simplify_mm: float = 0.15
    min_area_mm2: float = 0.2
    palette_mode: str = "strict"
    palette_tol: int = 0
    out_dir: Optional[str] = None
