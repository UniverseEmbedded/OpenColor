# API 定义

本文档定义 WebUI 与 Rust 后端之间的所有 API 接口。

## 数据结构定义

### 基础类型

```typescript
// 坐标点
interface Point {
  x: number;  // x坐标（像素）
  y: number;  // y坐标（像素）
}

// RGB颜色
interface Rgb {
  r: number;  // 红色分量 0-255
  g: number;  // 绿色分量 0-255
  b: number;  // 蓝色分量 0-255
}

// 工作区信息
interface WorkspaceInfo {
  path: string;        // 工作区绝对路径
  name: string;        // 显示名称
  createdAt: string;   // 创建时间 ISO 8601
}

// 任务进度
interface JobProgress {
  jobId: string;       // 任务唯一标识
  progress: number;    // 进度 0-1
  stage: string;       // 当前阶段描述
  message?: string;    // 可选状态消息
}

// 任务结果
interface JobResult<T> {
  jobId: string;       // 任务唯一标识
  result: T;           // 任务结果数据
}

// 任务错误
interface JobError {
  jobId: string;       // 任务唯一标识
  code: string;        // 错误代码
  message: string;     // 错误消息
  details?: any;       // 详细错误信息
}
```

### 环节相关类型

```typescript
// 校准板规格
interface BoardSpec {
  name: string;                    // 板子名称
  rows: number;                    // 行数
  cols: number;                    // 列数
  cellSizeMm: number;              // 格子尺寸毫米
  layerHeightMm: number;           // 层高毫米
  cells: BoardCell[];              // 格子数组
}

// 校准板格子
interface BoardCell {
  row: number;                     // 行索引
  col: number;                     // 列索引
  targetRgb: Rgb;                  // 目标颜色
  recipe: Record<string, number>;  // 耗材配方
}

// 校正参数
interface WarpParams {
  specPath: string;                // 规格文件路径
  cornerPoints: Point[];           // 四角坐标（左上、右上、右下、左下）
  rotationCount: number;           // 顺时针旋转90度次数
}

// 样本格子
interface SampleCell {
  row: number;                     // 行索引
  col: number;                     // 列索引
  enabled: boolean;                // 是否启用
  measuredRgb: Rgb;                // 测量颜色
  targetRgb: Rgb;                  // 目标颜色
  recipe: Record<string, number>;  // 耗材配方
}

// 训练配置
interface TrainingConfig {
  datasetPaths: string[];          // 数据集文件路径数组
  materialGroupId: string;         // 材料组标识
  layerHeightMm: number;           // 层高毫米
  opticalModel: 'rts' | 'four_flux' | 'tmm';  // 光学模型类型
  useVulkan: boolean;              // 是否使用Vulkan加速
  gprParams?: GprParams;           // GPR参数
}

// GPR参数
interface GprParams {
  kernel: string;                  // 核函数类型
  lengthScale: number;             // 长度尺度
  noiseLevel: number;              // 噪声水平
}

// 叠色像素配置
interface MaskGenConfig {
  imagePath: string;               // 输入图像路径
  modelPath: string;               // 颜色模型路径
  superresEnabled: boolean;        // 是否启用超分辨率
  superresScale: number;           // 超分辨率倍数
  layer0BiasEnabled: boolean;      // 是否启用首层偏向
  postprocessMode: 'joint' | 'none';  // 后处理模式
}

// 矢量化配置
interface VectorizeConfig {
  maskManifestPath: string;        // 掩码清单路径
  backend: 'cv2' | 'vtracer';      // 矢量化后端
  simplifyLevel: number;           // 简化级别
  resampleEnabled: boolean;        // 是否启用重采样
  reconcileEnabled: boolean;       // 是否启用栅格协调
}

// 导出配置
interface ExportConfig {
  vectorManifestPath: string;      // 矢量清单路径
  useCppAcceleration: boolean;     // 是否使用C++加速
  exportStl: boolean;              // 是否导出STL
  export3mf: boolean;              // 是否导出3MF
  meshRepairEnabled: boolean;      // 是否启用网格修复
}
```

---

## 工作区管理 API

### workspace_get_current

获取当前工作区路径

```typescript
// 输入：无
// 输出：
interface GetCurrentWorkspaceOutput {
  path: string;        // 当前工作区绝对路径，空字符串表示未设置
}
```

### workspace_set_current

设置当前工作区

```typescript
// 输入：
interface SetCurrentWorkspaceInput {
  path: string;        // 工作区绝对路径
}
// 输出：无
```

### workspace_create

创建新工作区

```typescript
// 输入：
interface CreateWorkspaceInput {
  parentPath: string;  // 父目录路径
  name: string;        // 工作区显示名称
}
// 输出：
interface CreateWorkspaceOutput {
  path: string;        // 新创建工作区的绝对路径
}
```

### workspace_list_recent

获取最近工作区列表

```typescript
// 输入：无
// 输出：
interface ListRecentWorkspacesOutput {
  workspaces: WorkspaceInfo[];  // 工作区信息数组，按最近使用排序
}
```

### workspace_remove_from_recent

从最近列表中移除（不删除实际目录）

```typescript
// 输入：
interface RemoveFromRecentInput {
  path: string;        // 要移除的工作区路径
}
// 输出：无
```

---

## 文件操作 API

### file_select_dialog

打开文件选择对话框

```typescript
// 输入：
interface SelectFileDialogInput {
  title?: string;              // 对话框标题
  multiple?: boolean;          // 是否允许多选
  filters?: FileFilter[];      // 文件过滤器
}

interface FileFilter {
  name: string;                // 过滤器显示名称
  extensions: string[];        // 扩展名数组，如 ["png", "jpg"]
}

// 输出：
interface SelectFileDialogOutput {
  paths: string[];             // 选中的文件路径数组，取消返回空数组
}
```

### file_select_folder_dialog

打开文件夹选择对话框

```typescript
// 输入：
interface SelectFolderDialogInput {
  title?: string;              // 对话框标题
}
// 输出：
interface SelectFolderDialogOutput {
  path: string;                // 选中的文件夹路径，取消返回空字符串
}
```

### file_read_text

读取文本文件内容（适用于小文件）

```typescript
// 输入：
interface ReadTextFileInput {
  path: string;                // 文件绝对路径
}
// 输出：
interface ReadTextFileOutput {
  content: string;             // 文件文本内容
}
```

### file_read_base64

读取文件为Base64（适用于中等文件）

```typescript
// 输入：
interface ReadBase64FileInput {
  path: string;                // 文件绝对路径
}
// 输出：
interface ReadBase64FileOutput {
  base64: string;              // Base64编码内容
  mimeType: string;            // MIME类型
}
```

### file_get_asset_url

获取本地文件的访问URL（适用于大文件）

```typescript
// 输入：
interface GetAssetUrlInput {
  path: string;                // 文件绝对路径
}
// 输出：
interface GetAssetUrlOutput {
  url: string;                 // 可用于img/video标签的URL
}
```

### file_write_text

写入文本文件

```typescript
// 输入：
interface WriteTextFileInput {
  path: string;                // 文件绝对路径
  content: string;             // 文本内容
}
// 输出：无
```

### file_exists

检查文件是否存在

```typescript
// 输入：
interface FileExistsInput {
  path: string;                // 文件或目录绝对路径
}
// 输出：
interface FileExistsOutput {
  exists: boolean;             // 是否存在
  isFile: boolean;             // 是否是文件
  isDirectory: boolean;        // 是否是目录
}
```

---

## 环节1：校准板生成 API

### board_gen

生成校准板

```typescript
// 输入：
interface BoardGenInput {
  outputDir: string;           // 输出目录（工作区的calib_board目录）
  specName: string;            // 规格名称前缀
  numBoards: number;           // 生成板子数量
  shrink: number;              // 格子缩进量毫米
  layerHeightMm: number;       // 层高毫米
  includeApriltag: boolean;    // 是否包含AprilTag（预留）
  includeSideTriangles: boolean;  // 是否包含侧边白色三角形
}

// 输出：
interface BoardGenOutput {
  specPaths: string[];         // 生成的规格文件路径数组
  printPaths: string[];        // 生成的3MF打印文件路径数组
}
```

---

## 环节2：照片校正与样本提取 API

### photo_warp

执行照片透视校正

```typescript
// 输入：
interface PhotoWarpInput {
  specPath: string;            // 规格文件路径
  photoPath: string;           // 原始照片路径
  cornerPoints: Point[];       // 四角坐标（4个点）
  rotationCount: number;       // 顺时针旋转90度次数
  outputDir: string;           // 输出目录（工作区的calib_photo目录）
}

// 输出：
interface PhotoWarpOutput {
  warpedPath: string;          // 校正后图像路径
  overlayPath: string;         // 网格叠加图路径
  warpParamsPath: string;      // 校正参数JSON路径
}
```

### sample_extract

执行样本提取

```typescript
// 输入：
interface SampleExtractInput {
  warpedPath: string;          // 校正后图像路径
  specPath: string;            // 规格文件路径
  warpParamsPath: string;      // 校正参数路径
  outputDir: string;           // 输出目录（工作区的calib_sample目录）
}

// 输出：
interface SampleExtractOutput {
  datasetPath: string;         // 数据集JSON路径
  previewBeforePath: string;   // 校准前预览图路径
  previewAfterPath: string;    // 校准后预览图路径
  cellCount: number;           // 总格子数
  enabledCellCount: number;    // 启用格子数
}
```

### sample_update_cell

更新单个格子的启用状态

```typescript
// 输入：
interface SampleUpdateCellInput {
  datasetPath: string;         // 数据集文件路径
  row: number;                 // 行索引
  col: number;                 // 列索引
  enabled: boolean;            // 新的启用状态
}

// 输出：
interface SampleUpdateCellOutput {
  enabledCellCount: number;    // 更新后的启用格子数
}
```

---

## 环节3：模型训练 API（异步）

### model_train_start

启动模型训练任务

```typescript
// 输入：
interface ModelTrainStartInput {
  config: TrainingConfig;      // 训练配置
  outputDir: string;           // 输出目录（工作区的calib_model目录）
}

// 输出：
interface ModelTrainStartOutput {
  jobId: string;               // 任务唯一标识
}
```

### model_train_cancel

取消正在进行的训练任务

```typescript
// 输入：
interface ModelTrainCancelInput {
  jobId: string;               // 任务标识
}
// 输出：无
```

---

## 环节4：叠色像素生成 API（异步）

### mask_gen_start

启动叠色像素生成任务

```typescript
// 输入：
interface MaskGenStartInput {
  config: MaskGenConfig;       // 叠色像素配置
  outputDir: string;           // 输出目录（工作区的gen_masks目录）
}

// 输出：
interface MaskGenStartOutput {
  jobId: string;               // 任务唯一标识
}
```

### mask_gen_cancel

取消正在进行的叠色像素生成任务

```typescript
// 输入：
interface MaskGenCancelInput {
  jobId: string;               // 任务标识
}
// 输出：无
```

---

## 环节5：矢量化 API（异步）

### vectorize_start

启动矢量化任务

```typescript
// 输入：
interface VectorizeStartInput {
  config: VectorizeConfig;     // 矢量化配置
  outputDir: string;           // 输出目录（工作区的gen_vector目录）
}

// 输出：
interface VectorizeStartOutput {
  jobId: string;               // 任务唯一标识
}
```

### vectorize_cancel

取消正在进行的矢量化任务

```typescript
// 输入：
interface VectorizeCancelInput {
  jobId: string;               // 任务标识
}
// 输出：无
```

---

## 环节6：模型导出 API（异步）

### export_start

启动模型导出任务

```typescript
// 输入：
interface ExportStartInput {
  config: ExportConfig;        // 导出配置
  outputDir: string;           // 输出目录（工作区的gen_3mf目录）
}

// 输出：
interface ExportStartOutput {
  jobId: string;               // 任务唯一标识
}
```

### export_cancel

取消正在进行的导出任务

```typescript
// 输入：
interface ExportCancelInput {
  jobId: string;               // 任务标识
}
// 输出：无
```

---

## 素材库 API

### library_list_boards

列出所有校准板规格

```typescript
// 输入：
interface ListBoardsInput {
  workspacePath: string;       // 工作区路径
}
// 输出：
interface ListBoardsOutput {
  boards: BoardItem[];         // 校准板列表
}

interface BoardItem {
  path: string;                // 文件路径
  name: string;                // 显示名称
  rows: number;                // 行数
  cols: number;                // 列数
  modifiedAt: string;          // 修改时间
}
```

### library_list_models

列出所有训练好的模型

```typescript
// 输入：
interface ListModelsInput {
  workspacePath: string;       // 工作区路径
}
// 输出：
interface ListModelsOutput {
  models: ModelItem[];         // 模型列表
}

interface ModelItem {
  path: string;                // 文件路径
  name: string;                // 显示名称
  materialGroup: string;       // 材料组
  layerHeightMm: number;       // 层高毫米
  avgDeltaE: number;           // 平均DeltaE
  trainedAt: string;           // 训练时间
}
```

### library_list_material_groups

列出所有材料组

```typescript
// 输入：无（全局素材库）
// 输出：
interface ListMaterialGroupsOutput {
  groups: MaterialGroupItem[];  // 材料组列表
}

interface MaterialGroupItem {
  id: string;                  // 材料组标识
  name: string;                // 显示名称
  channelCount: number;        // 通道数
  slotCount: number;           // 槽位数
}
```

---

## 设置 API

### settings_get_app

获取APP设置

```typescript
// 输入：无
// 输出：
interface GetAppSettingsOutput {
  locale: string;              // 语言
  theme: string;               // 主题
  enginePath: string;          // 引擎路径
  gpuAcceleration: boolean;    // GPU加速
  logLevel: string;            // 日志级别
}
```

### settings_set_app

设置APP设置

```typescript
// 输入：
interface SetAppSettingsInput {
  locale?: string;             // 语言
  theme?: string;              // 主题
  enginePath?: string;         // 引擎路径
  gpuAcceleration?: boolean;   // GPU加速
  logLevel?: string;           // 日志级别
}
// 输出：无
```

### settings_get_project

获取项目设置（当前工作区）

```typescript
// 输入：无（使用当前工作区）
// 输出：
interface GetProjectSettingsOutput {
  defaultMaterialGroupId: string;     // 默认材料组ID
  defaultLayerHeightMm: number;       // 默认层高毫米
  defaultModelId: string;             // 默认模型ID
  exportPreferences: ExportPreferences;  // 导出偏好
  maskGenParams: MaskGenParams;       // 叠色像素参数
}

interface ExportPreferences {
  exportStl: boolean;          // 导出STL
  export3mf: boolean;          // 导出3MF
  useCppAcceleration: boolean; // C++加速
  meshRepair: boolean;         // 网格修复
}

interface MaskGenParams {
  superresEnabled: boolean;    // 超分辨率
  superresScale: number;       // 超分辨率倍数
  layer0BiasEnabled: boolean;  // 首层偏向
  postprocessMode: string;     // 后处理模式
}
```

### settings_set_project

设置项目设置

```typescript
// 输入：
interface SetProjectSettingsInput {
  defaultMaterialGroupId?: string;
  defaultLayerHeightMm?: number;
  defaultModelId?: string;
  exportPreferences?: ExportPreferences;
  maskGenParams?: MaskGenParams;
}
// 输出：无
```

---

## 事件定义

### engine:job_progress

任务进度更新

```typescript
// payload: JobProgress
{
  jobId: string;               // 任务标识
  progress: number;            // 进度 0-1
  stage: string;               // 当前阶段描述
  message?: string;            // 状态消息
}
```

### engine:job_complete

任务完成

```typescript
// payload: JobResult<any>
{
  jobId: string;               // 任务标识
  result: any;                 // 任务结果（根据任务类型不同）
}
```

### engine:job_error

任务失败

```typescript
// payload: JobError
{
  jobId: string;               // 任务标识
  code: string;                // 错误代码
  message: string;             // 错误消息
  details?: any;               // 详细错误信息
}
```

### workspace:changed

当前工作区切换

```typescript
// payload: { path: string }
{
  path: string;                // 新工作区路径
}
```

### engine:log

引擎日志输出

```typescript
// payload:
{
  level: 'debug' | 'info' | 'warn' | 'error';  // 日志级别
  message: string;             // 日志消息
  timestamp: string;           // 时间戳
}
```
