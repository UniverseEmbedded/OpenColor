use std::process::Command;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

use crate::utils::find_project_root;

/// GPU 检测结果
#[derive(Serialize, Deserialize, Debug)]
pub struct GpuCheckResult {
    pub available: bool,
    pub device_count: u32,
    pub device_names: Vec<String>,
    pub message: String,
}

/// 检测 GPU 可用性
#[tauri::command]
pub async fn check_gpu(app: AppHandle) -> Result<GpuCheckResult, String> {
    // 根据构建模式确定可执行文件路径
    let exe_path = if cfg!(debug_assertions) {
        let root = find_project_root();
        // 使用 solver 测试程序检测 GPU
        let solver_exe = root.join("cpp_module").join("build").join("Release").join("opencolor_solver.exe");
        let solver_debug = root.join("cpp_module").join("build").join("Debug").join("opencolor_solver.exe");
        if solver_exe.exists() {
            solver_exe
        } else if solver_debug.exists() {
            solver_debug
        } else {
            // 如果没有 solver，尝试使用 web_probe
            let probe_release = root.join("cpp_module").join("build").join("Release").join("opencolor_web_probe.exe");
            let probe_debug = root.join("cpp_module").join("build").join("Debug").join("opencolor_web_probe.exe");
            if probe_release.exists() {
                probe_release
            } else if probe_debug.exists() {
                probe_debug
            } else {
                return Ok(GpuCheckResult {
                    available: false,
                    device_count: 0,
                    device_names: vec![],
                    message: "未找到 C++ 程序，请先构建 cpp_module".to_string(),
                });
            }
        }
    } else {
        // 发布模式下从资源目录加载
        match app.path().resolve("resources/cpp/opencolor_solver.exe", tauri::path::BaseDirectory::Resource) {
            Ok(path) => path,
            Err(_) => {
                // 尝试使用 web_probe 作为备选
                match app.path().resolve("resources/cpp/opencolor_web_probe.exe", tauri::path::BaseDirectory::Resource) {
                    Ok(path) => path,
                    Err(e) => {
                        return Ok(GpuCheckResult {
                            available: false,
                            device_count: 0,
                            device_names: vec![],
                            message: format!("无法解析 C++ 程序路径: {e}"),
                        });
                    }
                }
            }
        }
    };

    // 执行 C++ 程序，传入 --check-gpu 参数
    let output = match Command::new(&exe_path)
        .args(["--check-gpu"])
        .output() {
        Ok(output) => output,
        Err(e) => {
            return Ok(GpuCheckResult {
                available: false,
                device_count: 0,
                device_names: vec![],
                message: format!("启动 C++ 程序失败: {e}"),
            });
        }
    };

    // 检查执行结果
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Ok(GpuCheckResult {
            available: false,
            device_count: 0,
            device_names: vec![],
            message: if stderr.is_empty() {
                "C++ 程序执行失败".to_string()
            } else {
                format!("C++ 程序执行失败: {stderr}")
            },
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    
    // 尝试解析 JSON 输出
    match serde_json::from_str::<GpuCheckResult>(&stdout) {
        Ok(result) => Ok(result),
        Err(_) => {
            // 如果解析失败，返回基本成功信息
            Ok(GpuCheckResult {
                available: true,
                device_count: 1,
                device_names: vec!["Vulkan Compute Device".to_string()],
                message: stdout,
            })
        }
    }
}

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
