use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};
use tauri::AppHandle;

// ============================================
// 类型定义
// ============================================

/// 坐标点
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

/// RGB颜色
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

/// 校准板列表项
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardItem {
    pub path: String,
    pub name: String,
    pub rows: i32,
    pub cols: i32,
    pub modified_at: String,
}

/// 校准板格子
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardCell {
    pub row: i32,
    pub col: i32,
    pub target_rgb: Rgb,
    pub recipe: std::collections::HashMap<String, f64>,
}

/// 校准板规格
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardSpec {
    pub name: String,
    pub rows: i32,
    pub cols: i32,
    pub cell_size_mm: f64,
    pub layer_height_mm: f64,
    pub cells: Vec<BoardCell>,
}

/// 训练配置
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct TrainingConfig {
    pub dataset_paths: Vec<String>,
    pub material_group_id: String,
    pub layer_height_mm: f64,
    pub optical_model: String,
    pub use_vulkan: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpr_params: Option<GprParams>,
}

/// GPR参数
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct GprParams {
    pub kernel: String,
    pub length_scale: f64,
    pub noise_level: f64,
}

/// 训练好的模型
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ModelItem {
    pub path: String,
    pub name: String,
    pub material_group: String,
    pub layer_height_mm: f64,
    pub avg_delta_e: f64,
    pub trained_at: String,
}

// ============================================
// API 实现
// ============================================

/// 生成校准板
#[tauri::command]
pub async fn board_gen(
    output_dir: String,
    spec_name: String,
    num_boards: i32,
    shrink: f64,
    layer_height_mm: f64,
    include_apriltag: bool,
    include_side_triangles: bool,
) -> Result<BoardGenOutput, String> {
    // TODO: 调用 Python 引擎执行实际的校准板生成
    // 目前返回模拟数据
    
    let mut spec_paths = Vec::new();
    let mut print_paths = Vec::new();
    
    for i in 0..num_boards {
        let board_char = (b'A' + i as u8) as char;
        let name = format!("{}_{}", spec_name.replace(" ", "_"), board_char);
        
        spec_paths.push(format!("{}/{}_board_spec.json", output_dir, name));
        print_paths.push(format!("{}/{}.3mf", output_dir, name));
    }
    
    Ok(BoardGenOutput {
        spec_paths,
        print_paths,
    })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardGenOutput {
    pub spec_paths: Vec<String>,
    pub print_paths: Vec<String>,
}

/// 照片透视校正
#[tauri::command]
pub async fn photo_warp(
    spec_path: String,
    photo_path: String,
    corner_points: Vec<Point>,
    rotation_count: i32,
    output_dir: String,
) -> Result<PhotoWarpOutput, String> {
    // TODO: 调用 Python 引擎执行实际的透视校正
    // 目前返回模拟数据
    
    let warped_path = format!("{}/board_warped.png", output_dir);
    let overlay_path = format!("{}/board_overlay.png", output_dir);
    let warp_params_path = format!("{}/warp.json", output_dir);
    
    Ok(PhotoWarpOutput {
        warped_path,
        overlay_path,
        warp_params_path,
    })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PhotoWarpOutput {
    pub warped_path: String,
    pub overlay_path: String,
    pub warp_params_path: String,
}

/// 样本提取
#[tauri::command]
pub async fn sample_extract(
    warped_path: String,
    spec_path: String,
    warp_params_path: String,
    output_dir: String,
) -> Result<SampleExtractOutput, String> {
    // TODO: 调用 Python 引擎执行实际的样本提取
    // 目前返回模拟数据
    
    let dataset_path = format!("{}/dataset_cells.json", output_dir);
    let preview_before_path = format!("{}/preview_before_calib.png", output_dir);
    let preview_after_path = format!("{}/preview_after_calib.png", output_dir);
    
    Ok(SampleExtractOutput {
        dataset_path,
        preview_before_path,
        preview_after_path,
        cell_count: 225, // 15x15
        enabled_cell_count: 225,
    })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SampleExtractOutput {
    pub dataset_path: String,
    pub preview_before_path: String,
    pub preview_after_path: String,
    pub cell_count: i32,
    pub enabled_cell_count: i32,
}

/// 更新单个格子的启用状态
#[tauri::command]
pub async fn sample_update_cell(
    dataset_path: String,
    row: i32,
    col: i32,
    enabled: bool,
) -> Result<SampleUpdateOutput, String> {
    // TODO: 读取数据集文件，更新指定格子的状态
    
    Ok(SampleUpdateOutput {
        enabled_cell_count: 225, // 更新后的启用格子数
    })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SampleUpdateOutput {
    pub enabled_cell_count: i32,
}

/// 启动模型训练
#[tauri::command]
pub async fn model_train_start(
    training_config: TrainingConfig,
    output_dir: String,
) -> Result<ModelTrainStartOutput, String> {
    // TODO: 调用 Python 引擎启动训练任务
    // 生成任务ID
    let job_id = format!("train_{}", chrono::Local::now().timestamp());
    
    Ok(ModelTrainStartOutput {
        job_id,
    })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ModelTrainStartOutput {
    pub job_id: String,
}

/// 取消模型训练
#[tauri::command]
pub async fn model_train_cancel(
    job_id: String,
) -> Result<(), String> {
    // TODO: 调用 Python 引擎取消训练任务
    
    Ok(())
}

/// 列出校准板
#[tauri::command]
pub async fn library_list_boards(
    workspace_path: String,
) -> Result<ListBoardsOutput, String> {
    let board_dir = Path::new(&workspace_path).join("01_board_gen");
    
    let mut boards = Vec::new();
    
    if board_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(&board_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("json") {
                    if let Ok(metadata) = entry.metadata() {
                        if let Ok(modified) = metadata.modified() {
                            let modified_at = modified
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap_or_default()
                                .as_secs();
                            
                            let name = path
                                .file_stem()
                                .and_then(|s| s.to_str())
                                .unwrap_or("unknown")
                                .to_string();
                            
                            // 尝试读取规格文件获取行列数
                            let (rows, cols) = if let Ok(content) = std::fs::read_to_string(&path) {
                                if let Ok(spec) = serde_json::from_str::<serde_json::Value>(&content) {
                                    (
                                        spec.get("rows").and_then(|v| v.as_i64()).unwrap_or(17) as i32,
                                        spec.get("cols").and_then(|v| v.as_i64()).unwrap_or(17) as i32,
                                    )
                                } else {
                                    (17, 17)
                                }
                            } else {
                                (17, 17)
                            };
                            
                            boards.push(BoardItem {
                                path: path.to_string_lossy().to_string(),
                                name,
                                rows,
                                cols,
                                modified_at: modified_at.to_string(),
                            });
                        }
                    }
                }
            }
        }
    }
    
    // 按修改时间排序
    boards.sort_by(|a, b| b.modified_at.cmp(&a.modified_at));
    
    Ok(ListBoardsOutput { boards })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ListBoardsOutput {
    pub boards: Vec<BoardItem>,
}

/// 列出训练好的模型
#[tauri::command]
pub async fn library_list_models(
    workspace_path: String,
) -> Result<ListModelsOutput, String> {
    let model_dir = Path::new(&workspace_path).join("04_model_train");
    
    let mut models = Vec::new();
    
    if model_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(&model_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("json") {
                    if let Ok(metadata) = entry.metadata() {
                        if let Ok(modified) = metadata.modified() {
                            let trained_at = modified
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap_or_default()
                                .as_secs();
                            
                            let name = path
                                .file_stem()
                                .and_then(|s| s.to_str())
                                .unwrap_or("unknown")
                                .to_string();
                            
                            // 尝试读取模型文件获取信息
                            let (material_group, layer_height_mm, avg_delta_e) = 
                                if let Ok(content) = std::fs::read_to_string(&path) {
                                    if let Ok(model) = serde_json::from_str::<serde_json::Value>(&content) {
                                        (
                                            model.get("material_group")
                                                .and_then(|v| v.as_str())
                                                .unwrap_or("default")
                                                .to_string(),
                                            model.get("layer_height_mm")
                                                .and_then(|v| v.as_f64())
                                                .unwrap_or(0.2),
                                            model.get("training_stats")
                                                .and_then(|v| v.get("avg_delta_e"))
                                                .and_then(|v| v.as_f64())
                                                .unwrap_or(0.0),
                                        )
                                    } else {
                                        ("default".to_string(), 0.2, 0.0)
                                    }
                                } else {
                                    ("default".to_string(), 0.2, 0.0)
                                };
                            
                            models.push(ModelItem {
                                path: path.to_string_lossy().to_string(),
                                name,
                                material_group,
                                layer_height_mm,
                                avg_delta_e,
                                trained_at: trained_at.to_string(),
                            });
                        }
                    }
                }
            }
        }
    }
    
    // 按训练时间排序
    models.sort_by(|a, b| b.trained_at.cmp(&a.trained_at));
    
    Ok(ListModelsOutput { models })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ListModelsOutput {
    pub models: Vec<ModelItem>,
}
