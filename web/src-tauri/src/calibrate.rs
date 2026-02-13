use std::path::Path;
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, State};

use crate::engine::EngineManager;

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
#[allow(dead_code)]
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
    #[serde(rename = "modifiedAt")]
    pub modified_at: String,
    #[serde(rename = "profileId")]
    pub profile_id: String,
    #[serde(rename = "profileName")]
    pub profile_name: String,
    #[serde(rename = "profileColors")]
    pub profile_colors: Vec<ColorDef>,
    // 新增字段：数据格数量
    #[serde(rename = "dataRows")]
    pub data_rows: i32,
    #[serde(rename = "dataCols")]
    pub data_cols: i32,
    // 新增字段：生成参数
    #[serde(rename = "cellSizeMm")]
    pub cell_size_mm: f64,
    #[serde(rename = "layerHeightMm")]
    pub layer_height_mm: f64,
    pub layers: i32,
}

/// 校准板格子
#[allow(dead_code)]
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardCell {
    pub row: i32,
    pub col: i32,
    #[serde(rename = "targetRgb")]
    pub target_rgb: Rgb,
    pub recipe: HashMap<String, f64>,
}

/// 校准板规格
#[allow(dead_code)]
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

/// 颜色定义
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ColorDef {
    pub name: String,
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

/// 耗材组（颜色配置）
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ColorProfile {
    pub id: String,
    pub name: String,
    pub description: String,
    pub colors: Vec<ColorDef>,
    pub marker_tl: String,
    pub marker_tr: String,
    pub marker_br: String,
    pub marker_bl: String,
}

// ============================================
// API 实现
// ============================================

/// 生成校准板
#[tauri::command]
pub async fn board_gen(
    profile_id: String,
    num_boards: i32,
    shrink: f64,
    layers: i32,
    layer_height_mm: f64,
    cell_size_mm: f64,
    data_rows: i32,
    data_cols: i32,
    workspace_path: Option<String>,
    engine: State<'_, EngineManager>,
    app: AppHandle,
) -> Result<BoardGenOutput, String> {

    // 获取耗材组信息
    let profiles = list_profiles().await?;
    let profile = profiles.profiles
        .into_iter()
        .find(|p| p.id == profile_id)
        .ok_or_else(|| format!("未找到耗材组: {}", profile_id))?;

    // 构建materials参数
    let materials: Vec<serde_json::Value> = profile.colors.iter().map(|c| {
        serde_json::json!({
            "name": c.name,
            "r": c.r,
            "g": c.g,
            "b": c.b,
        })
    }).collect();

    // 生成时间戳 - 整组色盘共享同一个时间戳
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();

    let mut spec_paths = Vec::new();
    let mut print_paths = Vec::new();
    let mut boards = Vec::new();

    // 生成每个校准板
    for i in 0..num_boards {
        let board_char = (b'A' + i as u8) as char;
        let name = format!("Board_{}", board_char);

        // 发送进度事件
        let _ = app.emit("board_gen:progress", serde_json::json!({
            "current": i + 1,
            "total": num_boards,
            "stage": "generating",
            "stageDescription": format!("正在生成色盘 {} ({}/{})", board_char, i + 1, num_boards)
        }));

        // 调用Python引擎生成校准板
        // 传递时间戳，让Python使用同一个时间戳文件夹
        let mut params = serde_json::json!({
            "materials": materials,
            "dataRows": data_rows,
            "dataCols": data_cols,
            "rows": data_rows + 2,  // 总格子数 = 数据格 + 2格边框
            "cols": data_cols + 2,
            "layers": layers,
            "cellSizeMm": cell_size_mm,
            "layerHeightMm": layer_height_mm,
            "shrink": shrink,
            "export_formats": ["3mf"],
            "file_name": name,
            "timestamp": timestamp,  // 整组共享时间戳
            "profile_id": profile_id,
        });

        // 如果提供了工作区路径，传递给Python引擎
        if let Some(ref ws_path) = workspace_path {
            params["workspace_path"] = serde_json::json!(ws_path);
        }

        // 发送请求到Python引擎
        let result = engine.send_request("board.generate".to_string(), params)
            .map_err(|e| format!("调用Python引擎失败: {}", e))?;

        // 解析结果获取文件路径
        let spec_path = result.get("board_spec_path")
            .and_then(|v| v.as_str())
            .ok_or("未返回规格文件路径")?;
        let print_path = result.get("standard_3mf")
            .and_then(|v| v.as_str())
            .ok_or("未返回3MF文件路径")?;

        spec_paths.push(spec_path.to_string());
        print_paths.push(print_path.to_string());

        // 构建BoardItem
        boards.push(BoardItem {
            path: spec_path.to_string(),
            name: name.clone(),
            rows: data_rows + 2,
            cols: data_cols + 2,
            modified_at: timestamp.clone(),
            profile_id: profile.id.clone(),
            profile_name: profile.name.clone(),
            profile_colors: profile.colors.clone(),
            data_rows,
            data_cols,
            cell_size_mm,
            layer_height_mm,
            layers,
        });
    }

    Ok(BoardGenOutput {
        spec_paths,
        print_paths,
        boards,
    })
}



#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardGenOutput {
    pub spec_paths: Vec<String>,
    pub print_paths: Vec<String>,
    pub boards: Vec<BoardItem>,
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
    let _ = (spec_path, photo_path, corner_points, rotation_count);

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
    let _ = (warped_path, spec_path, warp_params_path);

    // TODO: 调用 Python 引擎执行实际的样本提取
    // 目前返回模拟数据
    
    let dataset_path = format!("{}/dataset_cells.json", output_dir);
    let preview_before_path = format!("{}/preview_before_calib.png", output_dir);
    let preview_after_path = format!("{}/preview_after_calib.png", output_dir);
    
    Ok(SampleExtractOutput {
        dataset_path,
        preview_before_path,
        preview_after_path,
        cell_count: 576, // 24x24 数据格
        enabled_cell_count: 576,
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
    let _ = (dataset_path, row, col, enabled);

    // TODO: 读取数据集文件，更新指定格子的状态
    
    Ok(SampleUpdateOutput {
        enabled_cell_count: 576, // 更新后的启用格子数 (24x24)
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
    let _ = (training_config, output_dir);

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
    let _ = job_id;

    // TODO: 调用 Python 引擎取消训练任务
    
    Ok(())
}

fn build_palette_from_cell_map(cell_map: &serde_json::Value) -> Vec<String> {
    let mut palette_candidate: Option<Vec<String>> = None;
    let mut palette_len: i32 = -1;
    let mut idx_to_name: std::collections::HashMap<i64, String> = std::collections::HashMap::new();
    let mut max_idx: i64 = -1;

    let Some(cell_map_obj) = cell_map.as_object() else {
        return Vec::new();
    };

    for cell_data in cell_map_obj.values() {
        let Some(cell_obj) = cell_data.as_object() else {
            continue;
        };

        let layers = cell_obj.get("layers").and_then(|v| v.as_array());
        let slot_names = cell_obj.get("slot_names").and_then(|v| v.as_array());
        if layers.is_none() || slot_names.is_none() {
            continue;
        }

        let layers = layers.unwrap();
        let slot_names = slot_names.unwrap();

        let mut layer_indices: Vec<i64> = Vec::new();
        for v in layers {
            if let Some(i) = v.as_i64() {
                layer_indices.push(i);
            }
        }
        if layer_indices.is_empty() {
            continue;
        }

        let mut max_layer_idx = -1;
        for v in &layer_indices {
            if *v > max_layer_idx {
                max_layer_idx = *v;
            }
        }

        if slot_names.len() != layer_indices.len() && (slot_names.len() as i64) > max_layer_idx {
            if (slot_names.len() as i32) > palette_len {
                let candidate = slot_names
                    .iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect::<Vec<String>>();
                palette_len = candidate.len() as i32;
                palette_candidate = Some(candidate);
            }
        }

        for (layer_pos, idx) in layer_indices.iter().enumerate() {
            if layer_pos >= slot_names.len() {
                continue;
            }
            let Some(name) = slot_names[layer_pos].as_str() else {
                continue;
            };
            if *idx > max_idx {
                max_idx = *idx;
            }
            idx_to_name.entry(*idx).or_insert_with(|| name.to_string());
        }
    }

    if let Some(candidate) = palette_candidate {
        return candidate;
    }

    if max_idx >= 0 {
        let mut names = Vec::new();
        for i in 0..=max_idx {
            let name = idx_to_name
                .get(&i)
                .cloned()
                .unwrap_or_else(|| "White".to_string());
            names.push(name);
        }
        return names;
    }

    Vec::new()
}

fn match_profile_by_palette<'a>(palette: &[String], profiles: &'a [ColorProfile]) -> Option<&'a ColorProfile> {
    if palette.is_empty() {
        return None;
    }

    for profile in profiles {
        let profile_names: Vec<String> = profile.colors.iter().map(|c| c.name.clone()).collect();
        if profile_names == palette {
            return Some(profile);
        }
    }

    let palette_set: std::collections::HashSet<String> = palette.iter().cloned().collect();
    for profile in profiles {
        if profile.colors.len() != palette.len() {
            continue;
        }
        let profile_set: std::collections::HashSet<String> = profile.colors.iter().map(|c| c.name.clone()).collect();
        if profile_set == palette_set {
            return Some(profile);
        }
    }

    None
}

/// 列出校准板
#[tauri::command]
pub async fn library_list_boards(
    workspace_path: String,
) -> Result<ListBoardsOutput, String> {
    let board_dir = Path::new(&workspace_path).join("01_board_gen");
    let profiles = list_profiles().await?.profiles;
    
    let mut boards = Vec::new();
    
    if board_dir.exists() {
        // 遍历时间戳子文件夹
        if let Ok(timestamp_entries) = std::fs::read_dir(&board_dir) {
            for timestamp_entry in timestamp_entries.flatten() {
                let timestamp_path = timestamp_entry.path();
                if !timestamp_path.is_dir() {
                    continue;
                }
                
                let _timestamp = timestamp_path
                    .file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or("unknown")
                    .to_string();
                
                // 遍历该时间戳文件夹下的规格文件
                if let Ok(entries) = std::fs::read_dir(&timestamp_path) {
                    for entry in entries.flatten() {
                        let path = entry.path();
                        if path.extension().and_then(|s| s.to_str()) == Some("json")
                            && path
                                .file_name()
                                .and_then(|s| s.to_str())
                                .is_some_and(|s| s.ends_with("_board_spec.json"))
                        {
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
                                    
                                    // 尝试读取规格文件获取行列数和参数
                                    let (rows, cols, data_rows, data_cols, cell_size_mm, layer_height_mm, layers, profile_id, profile_name, profile_colors) = 
                                        if let Ok(content) = std::fs::read_to_string(&path) {
                                            if let Ok(spec) = serde_json::from_str::<serde_json::Value>(&content) {
                                                let r = spec.get("rows").and_then(|v| v.as_i64()).unwrap_or(26) as i32;
                                                let c = spec.get("cols").and_then(|v| v.as_i64()).unwrap_or(26) as i32;
                                                let dr = spec.get("data_cells").and_then(|v| v.as_i64()).unwrap_or((r - 2) as i64) as i32;
                                                let dc = spec.get("data_cells").and_then(|v| v.as_i64()).unwrap_or((c - 2) as i64) as i32;
                                                let csm = spec.get("cell_size_mm").and_then(|v| v.as_f64()).unwrap_or(4.0);
                                                let lhm = spec.get("layer_height_mm").and_then(|v| v.as_f64()).unwrap_or(0.12);
                                                let lay = spec.get("n_layers").and_then(|v| v.as_i64()).unwrap_or(5) as i32;
                                                let palette = spec
                                                    .get("cell_map")
                                                    .map(build_palette_from_cell_map)
                                                    .unwrap_or_default();
                                                let mut pid = String::new();
                                                let mut pname = String::new();
                                                let mut pcolors = Vec::new();
                                                if let Some(profile) = match_profile_by_palette(&palette, &profiles) {
                                                    pid = profile.id.clone();
                                                    pname = profile.name.clone();
                                                    let mut ordered = Vec::new();
                                                    for name in &palette {
                                                        if let Some(c) = profile.colors.iter().find(|c| &c.name == name) {
                                                            ordered.push(c.clone());
                                                        }
                                                    }
                                                    if ordered.len() == palette.len() {
                                                        pcolors = ordered;
                                                    } else {
                                                        pcolors = profile.colors.clone();
                                                    }
                                                }
                                                (r, c, dr, dc, csm, lhm, lay, pid, pname, pcolors)
                                            } else {
                                                (26, 26, 24, 24, 4.0, 0.12, 5, String::new(), String::new(), Vec::new())
                                            }
                                        } else {
                                            (26, 26, 24, 24, 4.0, 0.12, 5, String::new(), String::new(), Vec::new())
                                        };
                                    
                                    boards.push(BoardItem {
                                        path: path.to_string_lossy().to_string(),
                                        name,
                                        rows,
                                        cols,
                                        modified_at: modified_at.to_string(),
                                        profile_id,
                                        profile_name,
                                        profile_colors,
                                        data_rows,
                                        data_cols,
                                        cell_size_mm,
                                        layer_height_mm,
                                        layers,
                                    });
                                }
                            }
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

/// 删除校准板（同时删除规格文件和对应的3MF文件）
#[tauri::command]
pub async fn delete_board(path: String) -> Result<(), String> {
    let spec_path = Path::new(&path);

    // 删除规格文件
    if spec_path.exists() {
        std::fs::remove_file(spec_path)
            .map_err(|e| format!("删除规格文件失败: {}", e))?;
    }

    // 尝试删除对应的3MF文件
    let stem = spec_path.file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let parent = spec_path.parent();

    if let Some(parent_path) = parent {
        let print_path = parent_path.join(format!("{}.3mf", stem));
        if print_path.exists() {
            std::fs::remove_file(&print_path)
                .map_err(|e| format!("删除3MF文件失败: {}", e))?;
        }
    }

    Ok(())
}

/// 重命名校准板（同时重命名规格文件和对应的3MF文件）
#[tauri::command]
pub async fn rename_board(path: String, new_name: String) -> Result<(), String> {
    let spec_path = Path::new(&path);

    if !spec_path.exists() {
        return Err("规格文件不存在".to_string());
    }

    let parent = spec_path.parent()
        .ok_or("无法获取父目录")?;
    let old_stem = spec_path.file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("");

    // 构建新路径
    let new_spec_path = parent.join(format!("{}_board_spec.json", new_name));

    // 重命名规格文件
    std::fs::rename(&spec_path, &new_spec_path)
        .map_err(|e| format!("重命名规格文件失败: {}", e))?;

    // 尝试重命名对应的3MF文件
    let old_print_path = parent.join(format!("{}.3mf", old_stem));
    let new_print_path = parent.join(format!("{}_board.3mf", new_name));

    if old_print_path.exists() {
        std::fs::rename(&old_print_path, &new_print_path)
            .map_err(|e| format!("重命名3MF文件失败: {}", e))?;
    }

    Ok(())
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

/// 列出可用耗材组
#[tauri::command]
pub async fn list_profiles() -> Result<ListProfilesOutput, String> {
    // 预设耗材组数据
    let profiles = vec![
        ColorProfile {
            id: "rgb".to_string(),
            name: "RGB三原色".to_string(),
            description: "红绿蓝三原色配置".to_string(),
            colors: vec![
                ColorDef { name: "Red".to_string(), r: 255, g: 0, b: 0 },
                ColorDef { name: "Green".to_string(), r: 0, g: 255, b: 0 },
                ColorDef { name: "Blue".to_string(), r: 0, g: 0, b: 255 },
            ],
            marker_tl: "Red".to_string(),
            marker_tr: "Green".to_string(),
            marker_br: "Blue".to_string(),
            marker_bl: "Red".to_string(),
        },
        ColorProfile {
            id: "rybw".to_string(),
            name: "RYBW四色".to_string(),
            description: "红黄蓝白四色配置（适合基础彩色打印）".to_string(),
            colors: vec![
                ColorDef { name: "Red".to_string(), r: 255, g: 0, b: 0 },
                ColorDef { name: "Yellow".to_string(), r: 255, g: 255, b: 0 },
                ColorDef { name: "Blue".to_string(), r: 0, g: 0, b: 255 },
                ColorDef { name: "White".to_string(), r: 255, g: 255, b: 255 },
            ],
            marker_tl: "Blue".to_string(),
            marker_tr: "Red".to_string(),
            marker_br: "Blue".to_string(),
            marker_bl: "Yellow".to_string(),
        },
        ColorProfile {
            id: "rgbw".to_string(),
            name: "RGBW四色".to_string(),
            description: "红绿蓝白四色配置（光色混合）".to_string(),
            colors: vec![
                ColorDef { name: "Red".to_string(), r: 255, g: 0, b: 0 },
                ColorDef { name: "Green".to_string(), r: 0, g: 255, b: 0 },
                ColorDef { name: "Blue".to_string(), r: 0, g: 0, b: 255 },
                ColorDef { name: "White".to_string(), r: 255, g: 255, b: 255 },
            ],
            marker_tl: "Blue".to_string(),
            marker_tr: "Red".to_string(),
            marker_br: "Blue".to_string(),
            marker_bl: "Green".to_string(),
        },
        ColorProfile {
            id: "rgbwk".to_string(),
            name: "RGBWK五色".to_string(),
            description: "红绿蓝白黑五色配置".to_string(),
            colors: vec![
                ColorDef { name: "Red".to_string(), r: 255, g: 0, b: 0 },
                ColorDef { name: "Green".to_string(), r: 0, g: 255, b: 0 },
                ColorDef { name: "Blue".to_string(), r: 0, g: 0, b: 255 },
                ColorDef { name: "White".to_string(), r: 255, g: 255, b: 255 },
                ColorDef { name: "Black".to_string(), r: 0, g: 0, b: 0 },
            ],
            marker_tl: "Blue".to_string(),
            marker_tr: "Red".to_string(),
            marker_br: "Blue".to_string(),
            marker_bl: "Green".to_string(),
        },
        ColorProfile {
            id: "full_8".to_string(),
            name: "完整8色".to_string(),
            description: "RGB-CYM-WK完整八色配置".to_string(),
            colors: vec![
                ColorDef { name: "Red".to_string(), r: 255, g: 0, b: 0 },
                ColorDef { name: "Green".to_string(), r: 0, g: 255, b: 0 },
                ColorDef { name: "Blue".to_string(), r: 0, g: 0, b: 255 },
                ColorDef { name: "Cyan".to_string(), r: 0, g: 255, b: 255 },
                ColorDef { name: "Yellow".to_string(), r: 255, g: 255, b: 0 },
                ColorDef { name: "Magenta".to_string(), r: 255, g: 0, b: 255 },
                ColorDef { name: "White".to_string(), r: 255, g: 255, b: 255 },
                ColorDef { name: "Black".to_string(), r: 0, g: 0, b: 0 },
            ],
            marker_tl: "Blue".to_string(),
            marker_tr: "Red".to_string(),
            marker_br: "Blue".to_string(),
            marker_bl: "Yellow".to_string(),
        },
    ];
    
    Ok(ListProfilesOutput { profiles })
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ListProfilesOutput {
    pub profiles: Vec<ColorProfile>,
}

// ============================================
// RTS 颜色预测和预览 API
// ============================================

/// 校准板预览输出
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BoardPreviewOutput {
    pub cells: Vec<BoardCell>,
    pub profile: ColorProfile,
}

fn _color_index_by_name(profile: &ColorProfile, name: &str) -> Option<usize> {
    profile.colors.iter().position(|c| c.name == name)
}

fn _default_border_color_index(profile: &ColorProfile) -> usize {
    _color_index_by_name(profile, "White").unwrap_or(0)
}

fn _corner_color_name<'a>(profile: &'a ColorProfile, corner: &'a str) -> &'a str {
    match corner {
        "TL" => profile.marker_tl.as_str(),
        "TR" => profile.marker_tr.as_str(),
        "BR" => profile.marker_br.as_str(),
        "BL" => profile.marker_bl.as_str(),
        _ => profile.marker_tl.as_str(),
    }
}

fn _rgb_from_profile(profile: &ColorProfile, idx: usize) -> Result<Rgb, String> {
    let c = profile
        .colors
        .get(idx)
        .or_else(|| profile.colors.first())
        .ok_or_else(|| "耗材组没有颜色定义".to_string())?;
    Ok(Rgb { r: c.r, g: c.g, b: c.b })
}

/// 生成校准板预览数据
#[tauri::command]
pub async fn board_preview(
    profile_id: String,
    spec_path: String,
    engine: State<'_, EngineManager>,
) -> Result<BoardPreviewOutput, String> {
    // 获取耗材组信息
    let profiles = list_profiles().await?;
    let profile = profiles.profiles
        .into_iter()
        .find(|p| p.id == profile_id)
        .ok_or_else(|| format!("未找到耗材组: {}", profile_id))?;

    // 强制要求提供 spec_path
    let spec_path = spec_path.trim().to_string();
    if spec_path.is_empty() {
        return Err("spec_path 不能为空".to_string());
    }

    // 调用Python引擎获取预览数据，传入规格文件路径
    let params = serde_json::json!({
        "profile_id": profile_id,
        "spec_path": spec_path,
    });

    let result = engine.send_request("board.preview".to_string(), params)
        .map_err(|e| format!("调用Python引擎失败: {}", e))?;

    // 解析返回的cells数据
    let cells_data = result.get("cells")
        .and_then(|v| v.as_array())
        .ok_or("未返回格子数据")?;

    let mut cells = Vec::new();
    for cell_data in cells_data {
        let row = cell_data.get("row")
            .and_then(|v| v.as_i64())
            .ok_or("格子数据缺少row字段")? as i32;
        let col = cell_data.get("col")
            .and_then(|v| v.as_i64())
            .ok_or("格子数据缺少col字段")? as i32;

        let target_rgb_data = cell_data.get("target_rgb")
            .ok_or("格子数据缺少target_rgb字段")?;
        let target_rgb = Rgb {
            r: target_rgb_data.get("r")
                .and_then(|v| v.as_i64())
                .ok_or("target_rgb缺少r字段")? as u8,
            g: target_rgb_data.get("g")
                .and_then(|v| v.as_i64())
                .ok_or("target_rgb缺少g字段")? as u8,
            b: target_rgb_data.get("b")
                .and_then(|v| v.as_i64())
                .ok_or("target_rgb缺少b字段")? as u8,
        };

        // 解析recipe
        let recipe_data = cell_data.get("recipe")
            .ok_or("格子数据缺少recipe字段")?;
        let mut recipe_map = std::collections::HashMap::new();
        if let Some(recipe_obj) = recipe_data.as_object() {
            for (key, val) in recipe_obj {
                if let Some(num) = val.as_f64() {
                    recipe_map.insert(key.clone(), num);
                }
            }
        }

        cells.push(BoardCell {
            row,
            col,
            target_rgb,
            recipe: recipe_map,
        });
    }

    Ok(BoardPreviewOutput { cells, profile })
}

/// 单个配方颜色预测输入
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct RtsPredictInput {
    pub recipe: Vec<usize>,
    pub profile_id: String,
}

/// 单个配方颜色预测输出
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct RtsPredictOutput {
    pub rgb: Rgb,
}

/// 预测单个配方的颜色
#[tauri::command]
pub async fn rts_predict_single(
    input: RtsPredictInput,
    engine: State<'_, EngineManager>,
) -> Result<RtsPredictOutput, String> {
    // 获取耗材组信息
    let profiles = list_profiles().await?;
    let profile = profiles.profiles
        .into_iter()
        .find(|p| p.id == input.profile_id)
        .ok_or_else(|| format!("未找到耗材组: {}", input.profile_id))?;

    // 构建材料列表
    let materials: Vec<serde_json::Value> = profile
        .colors
        .iter()
        .map(|c| {
            serde_json::json!({
                "name": c.name,
                "r": c.r,
                "g": c.g,
                "b": c.b,
            })
        })
        .collect();

    // 调用Python引擎进行RTS颜色预测
    let params = serde_json::json!({
        "profile_id": input.profile_id,
        "materials": materials,
        "recipe": input.recipe,
    });

    let result = engine.send_request("rts.predict".to_string(), params)
        .map_err(|e| format!("调用Python引擎失败: {}", e))?;

    // 解析返回的RGB数据
    let rgb_data = result.get("rgb")
        .ok_or("未返回RGB数据")?;

    let rgb = Rgb {
        r: rgb_data.get("r")
            .and_then(|v| v.as_i64())
            .ok_or("RGB缺少r字段")? as u8,
        g: rgb_data.get("g")
            .and_then(|v| v.as_i64())
            .ok_or("RGB缺少g字段")? as u8,
        b: rgb_data.get("b")
            .and_then(|v| v.as_i64())
            .ok_or("RGB缺少b字段")? as u8,
    };

    Ok(RtsPredictOutput { rgb })
}
