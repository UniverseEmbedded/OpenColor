use std::path::{Path, PathBuf};

use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, FilePath};

/// Base64 编码的文件数据
#[derive(Serialize)]
pub struct FileBase64 {
    pub mime: String,
    pub data: String,
}

/// 根据文件扩展名猜测 MIME 类型
pub fn guess_mime(path: &Path) -> String {
    let ext = path.extension().and_then(|v| v.to_str()).unwrap_or("").to_lowercase();
    match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "webp" => "image/webp",
        "svg" => "image/svg+xml",
        "json" => "application/json",
        "txt" => "text/plain",
        "md" => "text/markdown",
        "stl" => "model/stl",
        "3mf" => "model/3mf",
        _ => "application/octet-stream",
    }
    .to_string()
}

/// 读取文件并返回 Base64 编码
#[tauri::command]
pub fn read_file_base64(path: String) -> Result<FileBase64, String> {
    let bytes = std::fs::read(&path).map_err(|e| {
        let msg = format!("读取文件失败: {e}");
        eprintln!("[错误] {msg}");
        msg
    })?;
    let mime = guess_mime(Path::new(&path));
    let data = STANDARD.encode(bytes);
    Ok(FileBase64 { mime, data })
}

/// 读取文本文件并返回字符串
#[tauri::command]
pub fn read_text_file(path: String) -> Result<String, String> {
    let content = std::fs::read_to_string(&path).map_err(|e| {
        let msg = format!("读取文本文件失败: {e}");
        eprintln!("[错误] {msg}");
        msg
    })?;
    Ok(content)
}

/// 保存文本文件
#[tauri::command]
pub fn save_text_file(path: String, content: String) -> Result<(), String> {
    // 确保父目录存在
    let path_buf = PathBuf::from(&path);
    if let Some(parent) = path_buf.parent() {
        std::fs::create_dir_all(parent).map_err(|e| {
            let msg = format!("创建目录失败: {e}");
            eprintln!("[错误] {msg}");
            msg
        })?;
    }

    std::fs::write(&path, content).map_err(|e| {
        let msg = format!("保存文本文件失败: {e}");
        eprintln!("[错误] {msg}");
        msg
    })?;
    Ok(())
}

/// 创建目录
#[tauri::command]
pub fn create_dir(path: String) -> Result<(), String> {
    std::fs::create_dir_all(&path).map_err(|e| {
        let msg = format!("创建目录失败: {e}");
        eprintln!("[错误] {msg}");
        msg
    })?;
    Ok(())
}

/// 检查文件是否存在
#[tauri::command]
pub fn file_exists(path: String) -> Result<bool, String> {
    Ok(Path::new(&path).exists())
}

/// 打开文件选择对话框
#[tauri::command]
pub async fn file_select_dialog(
    app: AppHandle,
    title: Option<String>,
    filters: Option<Vec<(String, Vec<String>)>>,
    multiple: Option<bool>,
) -> Result<Option<Vec<String>>, String> {
    let mut dialog = app.dialog().file();
    
    // 设置标题
    if let Some(t) = title {
        dialog = dialog.set_title(&t);
    }
    
    // 设置文件过滤器 - 将 Vec<String> 转换为 &[&str]
    if let Some(f) = filters {
        for (name, extensions) in f {
            let ext_refs: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            dialog = dialog.add_filter(name, &ext_refs);
        }
    }
    
    // 打开对话框
    let result = dialog.blocking_pick_file();
    
    match result {
        Some(FilePath::Path(path)) => {
            Ok(Some(vec![path.to_string_lossy().to_string()]))
        }
        Some(FilePath::Url(url)) => {
            Ok(Some(vec![url.to_string()]))
        }
        None => Ok(None),
    }
}

/// 打开文件夹选择对话框
#[tauri::command]
pub async fn file_select_folder_dialog(
    app: AppHandle,
    title: Option<String>,
) -> Result<Option<String>, String> {
    let dialog = app.dialog().file();
    
    // 设置标题
    let dialog = if let Some(t) = title {
        dialog.set_title(&t)
    } else {
        dialog
    };
    
    // 打开对话框
    let result = dialog.blocking_pick_folder();
    
    match result {
        Some(FilePath::Path(path)) => {
            Ok(Some(path.to_string_lossy().to_string()))
        }
        Some(FilePath::Url(url)) => {
            Ok(Some(url.to_string()))
        }
        None => Ok(None),
    }
}

/// 保存文件对话框
#[tauri::command]
pub async fn file_save_dialog(
    app: AppHandle,
    title: Option<String>,
    default_name: Option<String>,
    filters: Option<Vec<(String, Vec<String>)>>,
) -> Result<Option<String>, String> {
    let mut dialog = app.dialog().file();
    
    // 设置标题
    if let Some(t) = title {
        dialog = dialog.set_title(&t);
    }
    
    // 设置默认文件名
    if let Some(name) = default_name {
        dialog = dialog.set_file_name(&name);
    }
    
    // 设置文件过滤器 - 将 Vec<String> 转换为 &[&str]
    if let Some(f) = filters {
        for (name, extensions) in f {
            let ext_refs: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            dialog = dialog.add_filter(name, &ext_refs);
        }
    }
    
    // 打开对话框
    let result = dialog.blocking_save_file();
    
    match result {
        Some(FilePath::Path(path)) => {
            Ok(Some(path.to_string_lossy().to_string()))
        }
        Some(FilePath::Url(url)) => {
            Ok(Some(url.to_string()))
        }
        None => Ok(None),
    }
}

/// 保存应用设置
#[tauri::command]
pub fn save_settings(app: AppHandle, settings: Value) -> Result<(), String> {
    let path = app.path().app_local_data_dir().map_err(|e| e.to_string())?
        .join("settings.json");
    
    // 确保父目录存在
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let content = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    std::fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

/// 加载应用设置
#[tauri::command]
pub fn load_settings(app: AppHandle) -> Result<Value, String> {
    let path = app.path().app_local_data_dir().map_err(|e| e.to_string())?
        .join("settings.json");
    
    // 如果设置文件不存在则返回空对象
    if !path.exists() {
        return Ok(Value::Object(serde_json::Map::new()));
    }

    let content = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let settings = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    Ok(settings)
}
