use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Manager};
use std::collections::HashMap;

/// 工作区信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceInfo {
    pub id: String,
    pub name: String,
    pub path: String,
    pub created_at: i64,
    pub last_opened: i64,
}

/// 工作区索引结构
#[derive(Debug, Serialize, Deserialize)]
pub struct WorkspaceIndex {
    pub version: i32,
    pub created_at: i64,
    pub updated_at: i64,
    pub metadata: HashMap<String, Value>,
}

impl Default for WorkspaceIndex {
    fn default() -> Self {
        let now = chrono::Local::now().timestamp();
        Self {
            version: 1,
            created_at: now,
            updated_at: now,
            metadata: HashMap::new(),
        }
    }
}

/// 获取应用数据目录
fn get_app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_local_data_dir().map_err(|e| e.to_string())
}

/// 获取工作区根目录
fn get_workspaces_root(app: &AppHandle) -> Result<PathBuf, String> {
    let app_data = get_app_data_dir(app)?;
    Ok(app_data.join("workspaces"))
}

/// 获取当前工作区路径
#[tauri::command]
pub fn workspace_get_current(app: AppHandle) -> Result<Option<String>, String> {
    let settings_path = get_app_data_dir(&app)?.join("app_settings.json");
    
    if !settings_path.exists() {
        return Ok(None);
    }
    
    let content = std::fs::read_to_string(&settings_path).map_err(|e| e.to_string())?;
    let settings: Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    
    Ok(settings.get("current_workspace")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string()))
}

/// 设置当前工作区
#[tauri::command]
pub fn workspace_set_current(app: AppHandle, path: String) -> Result<(), String> {
    let settings_path = get_app_data_dir(&app)?.join("app_settings.json");
    
    // 读取现有设置或创建新设置
    let mut settings: Value = if settings_path.exists() {
        let content = std::fs::read_to_string(&settings_path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())?
    } else {
        serde_json::json!({})
    };
    
    // 更新当前工作区
    settings["current_workspace"] = serde_json::json!(path);
    
    // 保存设置
    let content = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    std::fs::write(&settings_path, content).map_err(|e| e.to_string())?;
    
    Ok(())
}

/// 创建工作区
#[tauri::command]
pub fn workspace_create(
    app: AppHandle,
    name: Option<String>,
    custom_path: Option<String>,
) -> Result<WorkspaceInfo, String> {
    let workspaces_root = get_workspaces_root(&app)?;
    
    // 确定工作区路径
    let workspace_path = if let Some(custom) = custom_path {
        PathBuf::from(custom)
    } else {
        // 使用时间戳生成默认名称
        let default_name = name.unwrap_or_else(|| {
            let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
            format!("workspace_{}", timestamp)
        });
        workspaces_root.join(&default_name)
    };
    
    // 检查工作区是否已存在
    if workspace_path.exists() {
        return Err("工作区已存在".to_string());
    }
    
    // 创建工作区目录结构 (7个环节)
    let dirs = [
        "01_board_gen",      // 环节1：校准板生成
        "02_photo_warp",     // 环节2：照片校正
        "03_sample_build",   // 环节3：样本提取
        "04_model_train",    // 环节4：模型训练
        "05_mask_gen",       // 环节5：叠色像素生成
        "06_vectorize",      // 环节6：矢量化
        "07_export",         // 环节7：模型导出
    ];
    
    for dir in &dirs {
        std::fs::create_dir_all(workspace_path.join(dir)).map_err(|e| {
            format!("创建目录 {} 失败: {}", dir, e)
        })?;
    }
    
    // 创建 index.json
    let index = WorkspaceIndex::default();
    let index_path = workspace_path.join("index.json");
    let index_content = serde_json::to_string_pretty(&index).map_err(|e| e.to_string())?;
    std::fs::write(&index_path, index_content).map_err(|e| e.to_string())?;
    
    // 获取工作区名称
    let workspace_name = workspace_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unnamed")
        .to_string();
    
    let now = chrono::Local::now().timestamp();
    let workspace_info = WorkspaceInfo {
        id: workspace_name.clone(),
        name: workspace_name,
        path: workspace_path.to_string_lossy().to_string(),
        created_at: now,
        last_opened: now,
    };
    
    // 添加到最近工作区列表
    add_to_recent_workspaces(&app, &workspace_info)?;
    
    println!("[工作区] 创建工作区: {}", workspace_path.display());
    Ok(workspace_info)
}

/// 获取默认工作区路径
fn get_default_workspace_path(app: &AppHandle) -> Result<PathBuf, String> {
    let workspaces_root = get_workspaces_root(app)?;
    Ok(workspaces_root.join("default"))
}

/// 确保默认工作区存在
pub fn ensure_default_workspace(app: &AppHandle) -> Result<WorkspaceInfo, String> {
    let default_path = get_default_workspace_path(app)?;
    
    if !default_path.exists() {
        println!("[工作区] 创建默认工作区");
        workspace_create(app.clone(), Some("default".to_string()), None)
    } else {
        let now = chrono::Local::now().timestamp();
        Ok(WorkspaceInfo {
            id: "default".to_string(),
            name: "default".to_string(),
            path: default_path.to_string_lossy().to_string(),
            created_at: now,
            last_opened: now,
        })
    }
}

/// 列出最近工作区
#[tauri::command]
pub fn workspace_list_recent(app: AppHandle) -> Result<Vec<WorkspaceInfo>, String> {
    let recent_path = get_app_data_dir(&app)?.join("recent_workspaces.json");
    
    if !recent_path.exists() {
        return Ok(vec![]);
    }
    
    let content = std::fs::read_to_string(&recent_path).map_err(|e| e.to_string())?;
    let recent: Vec<WorkspaceInfo> = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    
    Ok(recent)
}

/// 添加到最近工作区列表
fn add_to_recent_workspaces(app: &AppHandle, workspace: &WorkspaceInfo) -> Result<(), String> {
    let recent_path = get_app_data_dir(app)?.join("recent_workspaces.json");
    
    // 读取现有列表
    let mut recent: Vec<WorkspaceInfo> = if recent_path.exists() {
        let content = std::fs::read_to_string(&recent_path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())?
    } else {
        vec![]
    };
    
    // 移除已存在的相同工作区
    recent.retain(|w| w.path != workspace.path);
    
    // 添加到开头
    let mut workspace_clone = workspace.clone();
    workspace_clone.last_opened = chrono::Local::now().timestamp();
    recent.insert(0, workspace_clone);
    
    // 只保留最近 10 个
    recent.truncate(10);
    
    // 保存
    let content = serde_json::to_string_pretty(&recent).map_err(|e| e.to_string())?;
    std::fs::write(&recent_path, content).map_err(|e| e.to_string())?;
    
    Ok(())
}

/// 从最近列表移除
#[tauri::command]
pub fn workspace_remove_from_recent(app: AppHandle, path: String) -> Result<(), String> {
    // 检查是否是默认工作区
    if path.contains("default") || path.ends_with("default") {
        return Err("默认工作区不能从最近列表移除".to_string());
    }
    
    let recent_path = get_app_data_dir(&app)?.join("recent_workspaces.json");
    
    if !recent_path.exists() {
        return Ok(());
    }
    
    let content = std::fs::read_to_string(&recent_path).map_err(|e| e.to_string())?;
    let mut recent: Vec<WorkspaceInfo> = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    
    recent.retain(|w| w.path != path);
    
    let content = serde_json::to_string_pretty(&recent).map_err(|e| e.to_string())?;
    std::fs::write(&recent_path, content).map_err(|e| e.to_string())?;
    
    Ok(())
}

/// 初始化工作区（在应用启动时调用）
pub fn init_workspace(app: &AppHandle) -> Result<WorkspaceInfo, String> {
    // 尝试获取当前工作区
    let current = workspace_get_current(app.clone())?;
    
    if let Some(path) = current {
        // 检查工作区是否仍然存在
        if Path::new(&path).exists() {
            // 更新最近列表
            let info = WorkspaceInfo {
                id: Path::new(&path).file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("unnamed")
                    .to_string(),
                name: Path::new(&path).file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("unnamed")
                    .to_string(),
                path: path.clone(),
                created_at: chrono::Local::now().timestamp(),
                last_opened: chrono::Local::now().timestamp(),
            };
            add_to_recent_workspaces(app, &info)?;
            return Ok(info);
        }
    }
    
    // 创建或获取默认工作区
    let default = ensure_default_workspace(app)?;
    workspace_set_current(app.clone(), default.path.clone())?;
    
    Ok(default)
}
