use std::backtrace::Backtrace;
use std::time::Instant;

use tauri::Manager;

// 模块声明
mod library;
mod engine;
mod file_utils;
mod utils;
mod cpp_bridge;

// 重新导出库模块的公共类型
pub use library::{LibraryItem, LibraryIndex, parse_oc_short, display_from_short};

// 重新导出引擎管理器
pub use engine::EngineManager;

/// 应用入口点
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let start = Instant::now();
    println!("[初始化] 启动应用");
    
    // 设置 panic 钩子以捕获崩溃信息
    std::panic::set_hook(Box::new(|info| {
        let bt = Backtrace::force_capture();
        eprintln!("[崩溃] 捕获到 panic: {info}");
        eprintln!("[崩溃] 调用栈: {bt}");
    }));
    println!("[初始化] 已启用 panic 日志");
    
    tauri::Builder::default()
        .setup(move |app| {
            let setup_start = Instant::now();
            println!("[初始化] 开始设置 Tauri");
            
            // 初始化日志插件
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;
            
            // 管理引擎管理器状态
            app.manage(EngineManager::new(app.handle().clone()));
            
            println!("[初始化] Tauri 设置完成，耗时 {} ms", setup_start.elapsed().as_millis());
            println!("[初始化] 应用准备就绪，耗时 {} ms", start.elapsed().as_millis());
            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            engine::engine_request,
            engine::engine_restart,
            cpp_bridge::cpp_probe,
            file_utils::read_file_base64,
            file_utils::read_text_file,
            file_utils::save_text_file,
            file_utils::create_dir,
            file_utils::save_settings,
            file_utils::load_settings,
            library::init_library,
            library::get_library_index,
            library::list_album_files,
            library::list_library_files,
            library::import_to_library,
            library::get_library_paths,
            library::upsert_library_item
        ])
        .build(tauri::generate_context!())
        .expect("构建 Tauri 应用失败")
        .run(|app_handle, event| {
            // 处理应用退出事件，清理 Python 引擎
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<EngineManager>() {
                    println!("[信息] 正在清理 Python 引擎...");
                    if let Err(e) = state.shutdown() {
                        eprintln!("[错误] Python 引擎清理失败: {e}");
                    } else {
                        println!("[信息] Python 引擎清理完成");
                    }
                }
            }
        });
}

// ==================== 单元测试 ====================
#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    use crate::file_utils::guess_mime;
    use crate::library::{parse_oc_short, display_from_short, default_library_schema_version};

    // 测试文件 MIME 类型猜测
    #[test]
    fn test_guess_mime() {
        assert_eq!(guess_mime(Path::new("test.png")), "image/png");
        assert_eq!(guess_mime(Path::new("test.jpg")), "image/jpeg");
        assert_eq!(guess_mime(Path::new("test.jpeg")), "image/jpeg");
        assert_eq!(guess_mime(Path::new("test.webp")), "image/webp");
        assert_eq!(guess_mime(Path::new("test.svg")), "image/svg+xml");
        assert_eq!(guess_mime(Path::new("test.unknown")), "application/octet-stream");
    }

    // 测试 oc 文件名解析 - 标准格式
    #[test]
    fn test_parse_oc_short_standard() {
        let result = parse_oc_short("oc1_mg_4c_csRGBW.json");
        assert!(result.is_some());
        let short = result.unwrap();
        assert_eq!(short.get("scheme").unwrap().as_str().unwrap(), "oc1");
        assert_eq!(short.get("kind").unwrap().as_str().unwrap(), "mg");
        assert_eq!(short.get("variant").unwrap().as_str().unwrap(), "4c");
        assert_eq!(short.get("cs").unwrap().as_str().unwrap(), "RGBW");
    }

    // 测试 oc 文件名解析 - 带喷嘴宽度
    #[test]
    fn test_parse_oc_short_nozzle() {
        let result = parse_oc_short("oc1_fl_std_noz040.json");
        assert!(result.is_some());
        let short = result.unwrap();
        assert_eq!(short.get("kind").unwrap().as_str().unwrap(), "fl");
        assert_eq!(short.get("nozzle_width_mm").unwrap().as_f64().unwrap(), 0.4);
    }

    // 测试 oc 文件名解析 - 无效格式
    #[test]
    fn test_parse_oc_short_invalid() {
        assert!(parse_oc_short("invalid.json").is_none());
        assert!(parse_oc_short("").is_none());
        assert!(parse_oc_short("test_oc1_mg.json").is_none());
    }

    // 测试 display_key 生成 - 材料组
    #[test]
    fn test_display_from_short_material_group() {
        let short = serde_json::json!({
            "kind": "mg",
            "variant": "4c",
            "cs": "RGBW"
        });
        
        let result = display_from_short(&short);
        assert!(result.is_some());
        let (key, args) = result.unwrap();
        assert_eq!(key, "album.file.material_group");
        assert_eq!(args.get("cs").unwrap().as_str().unwrap(), "RGBW");
    }

    // 测试 display_key 生成 - 位图
    #[test]
    fn test_display_from_short_bitmap() {
        let short = serde_json::json!({
            "kind": "bm",
            "variant": "s"
        });
        
        let result = display_from_short(&short);
        assert!(result.is_some());
        let (key, _) = result.unwrap();
        assert_eq!(key, "album.file.bitmap.standard");
    }

    // 测试资源库 schema 版本
    #[test]
    fn test_default_library_schema_version() {
        assert_eq!(default_library_schema_version(), 2);
    }

    // 测试 LibraryItem 结构序列化
    #[test]
    fn test_library_item_serialization() {
        let item = library::LibraryItem {
            id: "test_id".to_string(),
            name: "test.json".to_string(),
            path: "Profiles/test.json".to_string(),
            kind: "profile".to_string(),
            ctime: 1234567890,
            short: Some(serde_json::json!({"kind": "mg"})),
            long: None,
            display_key: Some("album.file.material_group".to_string()),
            display_args: None,
        };

        let json = serde_json::to_string(&item).unwrap();
        assert!(json.contains("test_id"));
        assert!(json.contains("profile"));
    }

    // 测试 LibraryIndex 结构
    #[test]
    fn test_library_index_default() {
        let index: library::LibraryIndex = serde_json::from_str(r#"{"items": []}"#).unwrap();
        assert_eq!(index.schema_version, 2);
        assert!(index.items.is_empty());
    }
}
