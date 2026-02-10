use std::process::Command;

use tauri::{AppHandle, Manager};

use crate::utils::find_project_root;

/// 调用 C++ 探测程序
#[tauri::command]
pub async fn cpp_probe(payload: String, app: AppHandle) -> Result<String, String> {
    // 根据构建模式确定可执行文件路径
    let exe_path = if cfg!(debug_assertions) {
        let root = find_project_root();
        let release = root.join("cpp_module").join("build").join("Release").join("opencolor_web_probe.exe");
        let debug = root.join("cpp_module").join("build").join("Debug").join("opencolor_web_probe.exe");
        if release.exists() {
            release
        } else if debug.exists() {
            debug
        } else {
            let msg = "未找到 C++ 探测程序，请先构建 cpp_module".to_string();
            eprintln!("[错误] {msg}");
            return Err(msg);
        }
    } else {
        // 发布模式下从资源目录加载
        app
            .path()
            .resolve("resources/cpp/opencolor_web_probe.exe", tauri::path::BaseDirectory::Resource)
            .map_err(|e| {
                let msg = format!("无法解析 C++ 探测程序路径: {e}");
                eprintln!("[错误] {msg}");
                msg
            })?
    };

    // 执行 C++ 程序
    let output = Command::new(&exe_path)
        .args(["--payload", &payload])
        .output()
        .map_err(|e| {
            let msg = format!("启动 C++ 探测程序失败: {e}");
            eprintln!("[错误] {msg}");
            msg
        })?;

    // 检查执行结果
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let msg = if stderr.is_empty() {
            "C++ 探测程序执行失败".to_string()
        } else {
            format!("C++ 探测程序执行失败: {stderr}")
        };
        eprintln!("[错误] {msg}");
        return Err(msg);
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if stdout.is_empty() {
        let msg = "C++ 探测程序未返回任何输出".to_string();
        eprintln!("[错误] {msg}");
        return Err(msg);
    }

    Ok(stdout)
}
