use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Manager};

/// 资源库中的单个项目
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct LibraryItem {
    pub id: String,
    pub name: String,
    pub path: String,
    pub kind: String, // 类型: "image", "spec", "profile"
    pub ctime: u64,
    #[serde(default)]
    pub short: Option<Value>,
    #[serde(default)]
    pub long: Option<Value>,
    #[serde(default)]
    pub display_key: Option<String>,
    #[serde(default)]
    pub display_args: Option<Value>,
}

/// 资源库索引
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct LibraryIndex {
    #[serde(default = "default_library_schema_version")]
    pub schema_version: u32,
    #[serde(default)]
    pub items: Vec<LibraryItem>,
}

pub(crate) fn default_library_schema_version() -> u32 {
    2
}

/// 解析 OpenColor 文件名中的短格式信息
pub fn parse_oc_short(file_name: &str) -> Option<Value> {
    let stem = file_name.rsplit_once('.').map(|(s, _)| s).unwrap_or(file_name);
    let parts: Vec<&str> = stem.split('_').collect();
    // 新格式: oc1_<kind>_<variant>_<tokens...> (不再包含时间戳)
    if parts.len() < 3 {
        return None;
    }
    if parts[0] != "oc1" {
        return None;
    }

    let kind_code = parts[1];
    let variant = parts[2];

    let mut m = serde_json::Map::new();
    m.insert("scheme".to_string(), Value::String("oc1".to_string()));
    m.insert("kind".to_string(), Value::String(kind_code.to_string()));
    m.insert("variant".to_string(), Value::String(variant.to_string()));

    // 从第3部分开始解析 tokens (跳过了原本的时间戳位置)
    for token in parts.iter().skip(3) {
        if token.is_empty() {
            continue;
        }
        if let Some(cs) = token.strip_prefix("cs") {
            if !cs.is_empty() {
                m.insert("cs".to_string(), Value::String(cs.to_string()));
            }
            continue;
        }
        if let Some(noz) = token.strip_prefix("noz") {
            if let Ok(v) = noz.parse::<u32>() {
                let mm = (v as f64) / 100.0;
                m.insert("nozzle_width_mm".to_string(), Value::Number(serde_json::Number::from_f64(mm)?));
            }
            continue;
        }
        if let Some(lh) = token.strip_prefix("lh") {
            if let Ok(v) = lh.parse::<u32>() {
                let mm = (v as f64) / 100.0;
                m.insert("layer_height_mm".to_string(), Value::Number(serde_json::Number::from_f64(mm)?));
            }
            continue;
        }
        if let Some(t) = token.strip_prefix('t') {
            if let Ok(v) = t.parse::<u32>() {
                let mm = (v as f64) / 100.0;
                m.insert("thickness_mm".to_string(), Value::Number(serde_json::Number::from_f64(mm)?));
            }
            continue;
        }
        if let Some(w) = token.strip_prefix('w') {
            if let Ok(v) = w.parse::<u32>() {
                m.insert("width_mm".to_string(), Value::Number(serde_json::Number::from(v)));
            }
            continue;
        }
        if let Some(n) = token.strip_prefix('n') {
            if let Ok(v) = n.parse::<u32>() {
                m.insert("n_layers".to_string(), Value::Number(serde_json::Number::from(v)));
            }
            continue;
        }
        if let Some(h) = token.strip_prefix('i') {
            if !h.is_empty() {
                m.insert("src_hash".to_string(), Value::String(h.to_string()));
            }
            continue;
        }
    }

    Some(Value::Object(m))
}

/// 从短格式信息生成显示键值
pub fn display_from_short(short: &Value) -> Option<(String, Value)> {
    let kind = short.get("kind")?.as_str()?;
    let variant = short
        .get("variant")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    let mut args = serde_json::Map::new();
    if let Some(v) = short.get("cs") {
        args.insert("cs".to_string(), v.clone());
    }
    if let Some(v) = short.get("n_layers") {
        args.insert("n_layers".to_string(), v.clone());
    }
    if let Some(v) = short.get("width_mm") {
        args.insert("width_mm".to_string(), v.clone());
    }
    if let Some(v) = short.get("thickness_mm") {
        args.insert("thickness_mm".to_string(), v.clone());
    }

    if kind == "mg" {
        if !args.contains_key("cs") {
            let channels = if let Some(v) = short.get("channel_count").and_then(|v| v.as_u64()) {
                Some(v as u32)
            } else if let Some(v) = short.get("channelCount").and_then(|v| v.as_u64()) {
                Some(v as u32)
            } else if let Some(v) = variant.strip_suffix('c').and_then(|s| s.parse::<u32>().ok()) {
                Some(v)
            } else {
                None
            };

            let cs = match channels {
                Some(4) => "RGBW".to_string(),
                Some(8) => "WBRGBCMY".to_string(),
                Some(n) => format!("{}C", n),
                None => "未知".to_string(),
            };
            args.insert("cs".to_string(), Value::String(cs));
        }
        if let Some(v) = short.get("mg_index") {
            args.insert("index".to_string(), v.clone());
        }
        return Some(("album.file.material_group".to_string(), Value::Object(args)));
    }

    let key = match (kind, variant) {
        ("bm", "s") => "album.file.bitmap.standard",
        ("bm", "b") => "album.file.bitmap.bambu",
        ("sv", "s") => "album.file.svg.standard",
        ("sv", "b") => "album.file.svg.bambu",
        ("bd", _) => "album.file.board.generate",
        _ => return None,
    };

    Some((key.to_string(), Value::Object(args)))
}

/// 初始化资源库目录结构
#[tauri::command]
pub fn init_library(app: AppHandle) -> Result<String, String> {
    use std::time::Instant;
    let start = Instant::now();
    println!("[初始化] 资源库初始化开始");
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let root = doc_dir.join("OpenColor");
    
    // 需要创建的目录列表
    let dirs = [
        root.join(".index"),
        root.join("Captures"),
        root.join("BoardSpecs"),
        root.join("Profiles"),
        root.join("Exports/STL"),
        root.join("Exports/3MF/Standard"),
        root.join("Exports/3MF/Bambu"),
        root.join("Datasets"),
    ];

    // 创建所有必要的目录
    for dir in &dirs {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }

    // 如果索引文件不存在则创建空索引
    let index_path = root.join(".index/library.json");
    if !index_path.exists() {
        let index = LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        };
        let content = serde_json::to_string_pretty(&index).map_err(|e| e.to_string())?;
        std::fs::write(index_path, content).map_err(|e| e.to_string())?;
    }

    let elapsed = start.elapsed().as_millis();
    println!("[初始化] 资源库初始化完成，耗时 {} ms", elapsed);
    Ok(root.to_string_lossy().to_string())
}

/// 获取资源库索引
#[tauri::command]
pub fn get_library_index(app: AppHandle) -> Result<LibraryIndex, String> {
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let index_path = doc_dir.join("OpenColor/.index/library.json");

    // 如果索引文件不存在则返回空列表
    if !index_path.exists() {
        return Ok(LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        });
    }

    let content = std::fs::read_to_string(index_path).map_err(|e| e.to_string())?;
    let index: LibraryIndex = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    Ok(index)
}

/// 获取资源库文件列表（与相册使用相同的扫描逻辑）
#[tauri::command]
pub fn list_library_files(app: AppHandle) -> Result<Vec<LibraryItem>, String> {
    // 复用 list_album_files 的逻辑
    list_album_files(app)
}

/// 扫描资源库中的所有文件
#[tauri::command]
pub fn list_album_files(app: AppHandle) -> Result<Vec<LibraryItem>, String> {
    use std::time::Instant;
    let start = Instant::now();
    println!("[加载] 相册扫描开始");
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let root = doc_dir.join("OpenColor");
    
    // 如果根目录不存在则返回空列表
    if !root.exists() {
        return Ok(vec![]);
    }

    let index_path = root.join(".index/library.json");
    let mut index = if index_path.exists() {
        let content = std::fs::read_to_string(&index_path).map_err(|e| e.to_string())?;
        serde_json::from_str::<LibraryIndex>(&content).unwrap_or(LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        })
    } else {
        LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        }
    };

    let mut index_map: HashMap<String, LibraryItem> = HashMap::new();
    for it in index.items.drain(..) {
        index_map.insert(it.path.clone(), it);
    }

    let mut items = vec![];
    let mut index_changed = false;
    let mut next_mg_index: u64 = 1;
    for it in index_map.values() {
        let Some(short) = it.short.as_ref() else {
            continue;
        };
        let Some(v) = short.get("mg_index").and_then(|v| v.as_u64()) else {
            continue;
        };
        if v + 1 > next_mg_index {
            next_mg_index = v + 1;
        }
    }
    
    /// 递归遍历目录的辅助函数
    /// 使用相对路径存储（相对于 OpenColor 根目录）
    fn visit_dirs(
        dir: &Path,
        root: &Path,
        items: &mut Vec<LibraryItem>,
        index_map: &HashMap<String, LibraryItem>,
        index_changed: &mut bool,
        next_mg_index: &mut u64,
    ) -> std::io::Result<()> {
        if dir.is_dir() {
            for entry in std::fs::read_dir(dir)? {
                let entry = entry?;
                let path = entry.path();
                if path.is_dir() {
                    // 跳过隐藏目录和特殊目录
                    let dir_name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
                    if dir_name == ".index" || dir_name == "node_modules" || dir_name.starts_with('.') {
                        continue;
                    }
                    visit_dirs(&path, root, items, index_map, index_changed, next_mg_index)?;
                } else {
                    // 获取文件信息
                    let file_name = path.file_name().and_then(|n| n.to_str()).unwrap_or("unknown");
                    let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("");
                    let parent_name = path.parent().and_then(|p| p.file_name()).and_then(|n| n.to_str()).unwrap_or("");
                    
                    // 根据扩展名和父目录确定文件类型
                    let kind = match ext.to_lowercase().as_str() {
                        "png" | "jpg" | "jpeg" | "webp" | "svg" => {
                            if parent_name == "Captures" || parent_name == "Profiles" {
                                "color_plate"
                            } else {
                                "source_image"
                            }
                        },
                        "json" => "json",
                        "stl" | "3mf" => {
                            // 检查是否是色盘模型（路径中包含 board_generate 或 calibration_board）
                            let path_str = path.to_string_lossy().to_lowercase();
                            if path_str.contains("board_generate") || path_str.contains("calibration_board") || path_str.contains("calib") {
                                "board_model"
                            } else {
                                "model"
                            }
                        },
                        _ => "other",
                    };

                    // 获取文件创建/修改时间
                    let metadata = entry.metadata()?;
                    let ctime = metadata.created()
                        .or_else(|_| metadata.modified())
                        .unwrap_or(SystemTime::now())
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs();

                    // 计算相对路径（相对于 OpenColor 根目录）
                    let rel_path = path.strip_prefix(root)
                        .map(|p| p.to_string_lossy().to_string().replace('/', "\\"))
                        .unwrap_or_else(|_| path.to_string_lossy().to_string());

                    let rel_path_lower = rel_path.to_lowercase();
                    let is_profiles_json = kind == "json" && rel_path_lower.starts_with("profiles\\");
                    
                    let mut item = LibraryItem {
                        id: rel_path.clone(),
                        name: file_name.to_string(),
                        path: rel_path.clone(),
                        kind: kind.to_string(),
                        ctime,
                        short: None,
                        long: None,
                        display_key: None,
                        display_args: None,
                    };

                    if let Some(mut short) = parse_oc_short(file_name) {
                        if let Value::Object(ref mut m) = short {
                            let kind_code = m.get("kind").and_then(|v| v.as_str()).unwrap_or("");
                            
                            // 根据文件名中的 kind_code 更新 item.kind
                            // fl = filament (耗材), mg = material_group (材料组)
                            match kind_code {
                                "fl" => item.kind = "filament".to_string(),
                                "mg" => item.kind = "profile".to_string(),
                                _ => {}
                            }
                            
                            if kind_code == "mg" && is_profiles_json {
                                if !m.contains_key("mg_index") {
                                    if let Some(existing) = index_map.get(&rel_path) {
                                        if let Some(Value::Object(old)) = existing.short.as_ref() {
                                            if let Some(v) = old.get("mg_index") {
                                                m.insert("mg_index".to_string(), v.clone());
                                            }
                                        }
                                    }
                                    if !m.contains_key("mg_index") {
                                        m.insert("mg_index".to_string(), Value::Number(serde_json::Number::from(*next_mg_index)));
                                        *next_mg_index += 1;
                                    }
                                }

                                if !m.contains_key("channel_count") {
                                    if let Some(v) = m.get("variant").and_then(|v| v.as_str()) {
                                        if let Some(ch) = v.strip_suffix('c').and_then(|s| s.parse::<u32>().ok()) {
                                            m.insert("channel_count".to_string(), Value::Number(serde_json::Number::from(ch)));
                                        }
                                    }
                                }
                            }
                        }
                        item.short = Some(short.clone());
                        if let Some((k, a)) = display_from_short(&short) {
                            item.display_key = Some(k);
                            item.display_args = Some(a);
                        }
                    }

                    if let Some(existing) = index_map.get(&rel_path) {
                        match (&mut item.short, &existing.short) {
                            (None, Some(old_short)) => {
                                item.short = Some(old_short.clone());
                            }
                            (Some(Value::Object(cur)), Some(Value::Object(old))) => {
                                if !cur.contains_key("board_index") {
                                    if let Some(v) = old.get("board_index") {
                                        cur.insert("board_index".to_string(), v.clone());
                                    }
                                }
                                if !cur.contains_key("mg_index") {
                                    if let Some(v) = old.get("mg_index") {
                                        cur.insert("mg_index".to_string(), v.clone());
                                    }
                                }
                            }
                            _ => {}
                        }
                        if item.long.is_none() {
                            item.long = existing.long.clone();
                        }
                        if item.display_key.is_none() {
                            item.display_key = existing.display_key.clone();
                            item.display_args = existing.display_args.clone();
                        }
                    }

                    if item.display_key.is_none() {
                        if let Some(short) = item.short.as_ref() {
                            if let Some((k, a)) = display_from_short(short) {
                                item.display_key = Some(k);
                                item.display_args = Some(a);
                            }
                        }
                    }

                    if item.short.is_some() || item.long.is_some() {
                        *index_changed = true;
                    }

                    items.push(item);
                }
            }
        }
        Ok(())
    }

    visit_dirs(
        &root,
        &root,
        &mut items,
        &index_map,
        &mut index_changed,
        &mut next_mg_index,
    )
    .map_err(|e| e.to_string())?;
    
    // 按时间倒序排序
    items.sort_by(|a, b| b.ctime.cmp(&a.ctime));

    let elapsed = start.elapsed().as_millis();
    println!("[加载] 相册扫描完成，数量 {}，耗时 {} ms", items.len(), elapsed);

    if index_changed {
        let mut merged: HashMap<String, LibraryItem> = index_map;
        for it in &items {
            if it.short.is_none() && it.long.is_none() {
                continue;
            }
            match merged.get(&it.path) {
                Some(old) => {
                    if old.short != it.short || old.long != it.long || old.kind != it.kind {
                        merged.insert(it.path.clone(), it.clone());
                    }
                }
                None => {
                    merged.insert(it.path.clone(), it.clone());
                }
            }
        }

        let mut index_items: Vec<LibraryItem> = merged.into_values().collect();
        index_items.sort_by(|a, b| a.path.cmp(&b.path));
        let new_index = LibraryIndex {
            schema_version: default_library_schema_version(),
            items: index_items,
        };
        if let Ok(content) = serde_json::to_string_pretty(&new_index) {
            if let Err(e) = std::fs::write(&index_path, content) {
                println!("[加载] 写入资源库索引失败: {}", e);
            }
        } else {
            println!("[加载] 序列化资源库索引失败");
        }
    }

    Ok(items)
}

/// 导入文件到资源库
#[tauri::command]
pub fn import_to_library(app: AppHandle, src_path: String, kind: String) -> Result<LibraryItem, String> {
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let root = doc_dir.join("OpenColor");
    
    // 根据类型确定目标子目录
    let sub_dir = match kind.as_str() {
        "image" => "Captures",
        "spec" => "BoardSpecs",
        "profile" => "Profiles",
        _ => return Err("Invalid kind".to_string()),
    };

    let src = PathBuf::from(&src_path);
    if !src.exists() {
        return Err("Source file does not exist".to_string());
    }

    let file_name = src.file_name().ok_or("Invalid filename")?;
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
    
    // 生成唯一文件名以防冲突
    let dest_file_name = format!("{}_{}", now, file_name.to_string_lossy());
    let dest_path = root.join(sub_dir).join(&dest_file_name);
    
    // 复制文件到目标位置
    std::fs::copy(&src, &dest_path).map_err(|e| e.to_string())?;

    let item = LibraryItem {
        id: format!("item_{}_{}", now, rand::random::<u32>()),
        name: file_name.to_string_lossy().to_string(),
        path: dest_path.to_string_lossy().to_string(),
        kind,
        ctime: now,
        short: None,
        long: None,
        display_key: None,
        display_args: None,
    };

    // 更新索引文件
    let index_path = root.join(".index/library.json");
    let mut index = if index_path.exists() {
        let content = std::fs::read_to_string(&index_path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())?
    } else {
        LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        }
    };

    index.items.push(item.clone());
    let content = serde_json::to_string_pretty(&index).map_err(|e| e.to_string())?;
    std::fs::write(index_path, content).map_err(|e| e.to_string())?;

    Ok(item)
}

/// 获取资源库路径
#[tauri::command]
pub fn get_library_paths(app: AppHandle) -> Result<Value, String> {
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let lib_root = doc_dir.join("OpenColor");
    
    let paths = serde_json::json!({
        "root": lib_root.to_string_lossy().to_string(),
        "profiles": lib_root.join("Profiles").to_string_lossy().to_string(),
        "filaments": lib_root.join("Filaments").to_string_lossy().to_string(),
        "albums": lib_root.join("Albums").to_string_lossy().to_string(),
        "index": lib_root.join(".index").to_string_lossy().to_string(),
    });
    
    Ok(paths)
}

/// 添加或更新资源库项目
#[tauri::command]
pub fn upsert_library_item(
    app: AppHandle,
    path: String,
    kind: String,
    short: Option<Value>,
    long: Option<Value>,
) -> Result<(), String> {
    let doc_dir = app.path().document_dir().map_err(|e| e.to_string())?;
    let root = doc_dir.join("OpenColor");
    let index_path = root.join(".index/library.json");

    // 加载现有索引
    let mut index = if index_path.exists() {
        let content = std::fs::read_to_string(&index_path).map_err(|e| e.to_string())?;
        serde_json::from_str::<LibraryIndex>(&content).unwrap_or(LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        })
    } else {
        // 确保目录存在
        if let Some(parent) = index_path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        LibraryIndex {
            schema_version: default_library_schema_version(),
            items: vec![],
        }
    };

    // 获取文件信息
    let file_path = root.join(&path);
    let file_name = file_path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let ctime = if file_path.exists() {
        std::fs::metadata(&file_path)
            .ok()
            .and_then(|m| m.created().ok())
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0)
    } else {
        0
    };

    // 检查是否已存在
    let existing_pos = index.items.iter().position(|it| it.path == path);

    let item = LibraryItem {
        id: path.clone(),
        name: file_name,
        path: path.clone(),
        kind: kind.clone(),
        ctime,
        short,
        long,
        display_key: None,
        display_args: None,
    };

    if let Some(pos) = existing_pos {
        index.items[pos] = item;
    } else {
        index.items.push(item);
    }

    // 保存索引
    let json = serde_json::to_string_pretty(&index).map_err(|e| e.to_string())?;
    std::fs::write(&index_path, json).map_err(|e| e.to_string())?;

    Ok(())
}
