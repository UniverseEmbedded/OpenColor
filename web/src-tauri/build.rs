// Tauri 构建脚本
// 用于在编译时执行 Tauri 特定的构建步骤

fn main() {
  // 调用 tauri_build 的构建函数，处理资源编译和配置生成
  tauri_build::build()
}
