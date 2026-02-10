// 防止在 Windows 发布版本中出现额外的控制台窗口，不要删除!!
// #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  app_lib::run();
}
