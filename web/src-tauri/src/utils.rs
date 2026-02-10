use std::path::PathBuf;

/// 查找项目根目录
/// 向上遍历目录树，查找包含 py_module 或 pixi.toml 的目录
pub fn find_project_root() -> PathBuf {
    let mut dir = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    for _ in 0..6 {
        // 检查是否存在引擎主文件
        if dir.join("py_module").join("engine").join("src").join("oc_engine").join("main.py").exists() {
            return dir;
        }
        // 检查是否存在 pixi.toml 和 py_module 目录
        if dir.join("pixi.toml").exists() && dir.join("py_module").exists() {
            return dir;
        }
        if !dir.pop() {
            break;
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}
