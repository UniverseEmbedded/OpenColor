use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Instant;

use pyo3::prelude::*;
use pyo3::types::{PyCFunction, PyDict, PyList, PyModule, PyTuple};
use serde_json::Value;
use tauri::{AppHandle, Emitter, State};

use crate::utils::find_project_root;

/// Python 引擎进程结构
struct EngineProcess {
    bridge_module: Py<PyModule>,
}

/// 引擎管理器，负责 Python 引擎的生命周期
pub struct EngineManager {
    app: AppHandle,
    inner: Mutex<Option<EngineProcess>>,
}

impl EngineManager {
    /// 创建新的引擎管理器实例
    pub fn new(app: AppHandle) -> Self {
        Self {
            app,
            inner: Mutex::new(None),
        }
    }

    pub fn shutdown(&self) -> Result<(), String> {
        let mut guard = self.inner.lock().map_err(|_| "引擎锁失败".to_string())?;
        *guard = None;
        Ok(())
    }

    /// 查找项目根目录
    fn find_project_root(&self) -> PathBuf {
        find_project_root()
    }

    /// 启动 Python 引擎
    fn start_engine(&self) -> Result<(), String> {
        let start_total = Instant::now();
        let mut guard = self.inner.lock().map_err(|_| "引擎锁失败".to_string())?;
        // 如果引擎已启动则直接返回
        if guard.is_some() {
            return Ok(());
        }

        let root = self.find_project_root();
        println!("[信息] 项目根目录: {:?}", root);
        println!("[引擎] 初始化开始");

        // Python 模块搜索路径
        let py_paths = vec![
            root.join("py_module/engine/src"),
            root.join("py_module/opencolor/src"),
            root.join("py_module/model_export/src"),
            root.join("py_module/calibration/src"),
            root.join("py_module/analyze/src"),
            root.join("py_module/prototypes/src"),
            root.join("py_module/sdf/src"),
            root.join("py_module/xgb/src"),
            root.join("py_module/scripts/src"),
        ];

        Python::attach(|py| -> PyResult<()> {
            let t_py_attach = Instant::now();
            let sys = py.import("sys")?;
            let sys_path = sys.getattr("path")?;
            let path = sys_path.cast::<PyList>()?;
            
            // 将模块路径添加到 Python 搜索路径
            for p in py_paths {
                let p_str = p.to_string_lossy().to_string();
                if !path.contains(&p_str)? {
                    path.insert(0, p_str)?;
                }
            }

            println!("[引擎] Python 环境准备完成，耗时 {} ms", t_py_attach.elapsed().as_millis());

            // 导入桥接模块
            let t_import = Instant::now();
            let bridge = py.import("oc_engine.api_bridge")?;
            println!("[引擎] 导入 oc_engine.api_bridge 完成，耗时 {} ms", t_import.elapsed().as_millis());
            
            // 注册事件回调函数
            let app_handle = self.app.clone();
            let callback = PyCFunction::new_closure(py, None, None, move |args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>| -> PyResult<()> {
                let json_str: String = args.get_item(0)?.extract()?;
                
                // 解析 JSON 并分发事件到前端
                if let Ok(val) = serde_json::from_str::<Value>(&json_str) {
                    if let Some(evt) = val.get("event").and_then(|v| v.as_str()) {
                        let channel = match evt {
                            "job.progress" => "engine://job_progress",
                            "job.done" => "engine://job_done",
                            "job.error" => "engine://job_error",
                            _ => "engine://log",
                        };
                        let _ = app_handle.emit(channel, val);
                    }
                }
                Ok(())
            })?;

            // 注册日志回调函数
            let app_log = self.app.clone();
            let log_callback = PyCFunction::new_closure(py, None, None, move |args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>| -> PyResult<()> {
                let stream_name: String = args.get_item(0)?.extract()?;
                let message: String = args.get_item(1)?.extract()?;
                
                let _ = app_log.emit("engine://log", serde_json::json!({
                    "level": stream_name,
                    "message": message
                }));
                Ok(())
            })?;
            
            bridge.call_method1("register_callback", (callback, log_callback))?;
            println!("[引擎] 注册回调完成");
            
            // 执行 ping 测试确认引擎正常工作
            let t_ping = Instant::now();
            let ping_res: String = bridge.call_method0("ping")?.extract()?;
            println!("[信息] 引擎初始化 Ping 结果: {}", ping_res);
            println!("[引擎] Ping 完成，耗时 {} ms", t_ping.elapsed().as_millis());
            
            // 保存引擎进程引用
            *guard = Some(EngineProcess {
                bridge_module: bridge.unbind(),
            });

            println!("[信息] PyO3 引擎初始化成功");
            println!("[引擎] 初始化结束，总耗时 {} ms", start_total.elapsed().as_millis());
            Ok(())
        }).map_err(|e| {
            let msg = format!("Python 初始化失败: {e}");
            eprintln!("[错误] {msg}");
            msg
        })?;

        Ok(())
    }

    /// 重启 Python 引擎
    fn restart_engine(&self) -> Result<(), String> {
        let mut guard = self.inner.lock().map_err(|_| "引擎锁失败".to_string())?;
        *guard = None; // 丢弃旧的模块引用，PyO3 会处理引用计数
        drop(guard);
        self.start_engine()
    }

    /// 向引擎发送请求
    pub fn send_request(&self, method: String, params: Value) -> Result<Value, String> {
        self.start_engine()?;
        
        let params_json = serde_json::to_string(&params).map_err(|e| e.to_string())?;

        let result_json = Python::attach(|py| -> PyResult<String> {
            let guard = self.inner.lock().map_err(|_| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("引擎锁失败"))?;
            let proc = guard.as_ref().ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("引擎未启动"))?;
            
            let bridge = proc.bridge_module.bind(py);
            let dispatch_fn = bridge.getattr("dispatch_json")?;
            
            // 调用 Python 桥接函数
            let res: String = dispatch_fn.call1((method, params_json))?.extract()?;
            Ok(res)
        }).map_err(|e| format!("Python 调用失败: {e}"))?;

        let val: Value = serde_json::from_str(&result_json).map_err(|e| format!("解析结果失败: {e}"))?;
        
        // 检查是否有错误返回
        if let Some(err) = val.get("error") {
            return Err(err.as_str().unwrap_or("未知错误").to_string());
        }
        
        Ok(val)
    }
}

/// 向引擎发送请求的命令
#[tauri::command]
pub async fn engine_request(method: String, params: Value, state: State<'_, EngineManager>) -> Result<Value, String> {
    println!("[请求] method={}, params={}", method, params);
    match state.send_request(method, params) {
        Ok(res) => {
            println!("[响应] 成功");
            Ok(res)
        }
        Err(e) => {
            eprintln!("[响应] 失败: {}", e);
            Err(e)
        }
    }
}

/// 重启引擎的命令
#[tauri::command]
pub async fn engine_restart(state: State<'_, EngineManager>) -> Result<(), String> {
    state.restart_engine().map_err(|e| format!("重启引擎失败: {e}"))
}
