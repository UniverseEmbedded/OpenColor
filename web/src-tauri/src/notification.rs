use serde::{Deserialize, Serialize};
use tauri_plugin_notification::NotificationExt;

/// 通知选项
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct NotificationOptions {
    pub title: String,
    pub body: String,
}

/// 显示系统通知
#[tauri::command]
pub async fn show_notification(
    app: tauri::AppHandle,
    options: NotificationOptions,
) -> Result<(), String> {
    app.notification()
        .builder()
        .title(&options.title)
        .body(&options.body)
        .show()
        .map_err(|e| format!("显示通知失败: {}", e))
}
