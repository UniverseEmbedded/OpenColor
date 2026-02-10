import { useTauriBridge } from "./useTauriBridge";
import { enqueueMessage } from "./useMessageQueue";

/**
 * 引擎操作组合式函数
 * 封装了所有与后端引擎交互的异步请求逻辑
 *
 * @param {Object} state - 应用程序全局状态对象
 * @param {Function} t - 国际化翻译函数
 * @param {Function} toastShow - 显示吐司提示的函数
 * @param {Function} invoke - Tauri 调用函数
 * @param {Function} joinPaths - 路径拼接函数
 */
export const useEngineOps = (state, t, toastShow, invoke, joinPaths) => {
  /**
   * 测试引擎连接 (Ping)
   */
  const pingEngine = async () => {
    try {
      const result = await invoke("engine_request", { method: "health.ping", params: {} });
      console.log(`${t("status.connected")}${JSON.stringify(result)}`);
      toastShow(t("toast.pingSuccess"), t("toast.pingSuccessDesc"));
    } catch (e) {
      const msg = `${t("toast.pingFail")}: ${e}`;
      console.error(msg);
      toastShow(t("toast.pingFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 运行 LUT 提取任务
   * 从拍摄的照片中提取颜色查找表
   */
  const runLutExtract = async () => {
    state.lutStatus.value = "";
    state.lutResultSummary.value = "";
    state.lutResultFile.value = "";
    state.lutOverlayPath.value = "";
    state.lutWarpedPath.value = "";
    let points = null;
    try {
      points = JSON.parse(state.lutCornerPoints.value || "[]");
    } catch (e) {
      const msg = t("toast.jsonParseFail");
      console.error(msg, e);
      toastShow(t("toast.paramError"), msg);
      return;
    }
    try {
      const result = await invoke("engine_request", {
        method: "lut.extract_from_photo",
        params: {
          photo_path: state.lutPhotoPath.value,
          corner_points: points,
          board_spec_path: state.boardSpecPath.value || undefined,
          out_dir: state.lutOutDir.value || undefined,
          zoom: Number(state.lutZoom.value),
          barrel: Number(state.lutBarrel.value),
          offset_x: Number(state.lutOffsetX.value),
          offset_y: Number(state.lutOffsetY.value),
          auto_wb: Boolean(state.lutAutoWb.value),
          vignette_fix: Boolean(state.lutVignetteFix.value),
          window_px: Number(state.lutWindowPx.value),
        },
      });
      state.lutJobId.value = result.job_id || "";
      state.lutOutDir.value = result.out_dir || state.lutOutDir.value;
      state.lutStatus.value = `${t("status.submitted")}${state.lutJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.lutStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 运行自动点位检测
   * 自动识别照片中的标靶四个角点
   */
  const runLutDetect = async () => {
    if (!state.lutPhotoPath.value) {
      toastShow(t("toast.paramError"), t("hint.calibPhotoPlaceholder"));
      return;
    }
    state.lutStatus.value = t("status.detecting");
    try {
      const result = await invoke("engine_request", {
        method: "lut.detect_points",
        params: {
          photo_path: state.lutPhotoPath.value,
        },
      });
      state.lutJobId.value = result.job_id || "";
      state.lutStatus.value = `${t("status.submitted")}${state.lutJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.lutStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 生成标靶文件 (STL/3MF)
   * @param {Object} options 生成选项
   * @param {number} options.rows 行数
   * @param {number} options.cols 列数
   * @param {number} options.tileSizeMm 单元格尺寸(mm)
   * @param {number} options.layerHeightMm 层高(mm)
   * @param {number} options.layers 层数
   * @param {number} options.shrink 收缩率
   * @param {string} options.fileName 文件名
   * @param {Array} options.materials 材料配置 [{name, rgba}, ...]
   * @param {Array} options.exportFormats 导出格式 ["3mf", "stl"]
   */
  const runBoardGenerate = async (options = {}) => {
    state.lutStatus.value = t("status.generatingBoard");
    try {
      // 构建参数，优先使用传入的参数，否则使用默认值
      const params = {
        // 旧版参数（兼容）
        color_system: options.color_system || "RYBW",
        n_layers: options.n_layers || options.layers || 5,
        cell_size_mm: options.cell_size_mm || options.tileSizeMm || 6.0,
        layer_height_mm: options.layer_height_mm || options.layerHeightMm || 0.12,
        total_cells: options.total_cells || 34,
        data_cells: options.data_cells || 32,
        // 新版参数（支持材料配置）
        rows: options.rows || 15,
        cols: options.cols || 15,
        layers: options.layers || 5,
        tileSizeMm: options.tileSizeMm || 6.0,
        tile_size_mm: options.tile_size_mm || options.tileSizeMm || 6.0,
        layerHeightMm: options.layerHeightMm || 0.12,
        layer_height_mm: options.layer_height_mm || options.layerHeightMm || 0.12,
        shrink: options.shrink || 0.0,
        fileName: options.fileName || options.file_name || "",
        file_name: options.file_name || options.fileName || "",
        // 材料配置（如果提供）
        materials: options.materials || null,
        // 导出格式
        export_formats: options.export_formats || options.exportFormats || ["3mf"],
        exportFormats: options.exportFormats || options.export_formats || ["3mf"],
      };

      console.log("[引擎] 调用 board.generate 参数:", params);

      const result = await invoke("engine_request", {
        method: "board.generate",
        params: params,
      });
      state.lutJobId.value = result.job_id || "";
      console.log("[引擎] board.generate 已提交, JobId:", state.lutJobId.value);
      state.lutStatus.value = `${t("status.submitted")}${state.lutJobId.value}`;
      toastShow(t("toast.generate"), t("status.submitted"));
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.lutStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 生成快速校色卡
   */
  const runQuickCalibCardGenerate = async () => {
    state.lutStatus.value = t("status.generatingCard");
    try {
      const result = await invoke("engine_request", {
        method: "quick_calib.generate_card",
        params: {
          w: 120.0,
          h: 80.0,
          t_min: 0.20,
          t_max: 1.20,
          feet: true,
          ribs: true,
        },
      });
      state.lutJobId.value = result.job_id || "";
      state.lutStatus.value = `${t("status.submitted")}${state.lutJobId.value}`;
      toastShow(t("toast.generate"), t("status.submitted"));
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.lutStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 创建新数据集
   */
  const runDatasetCreate = async () => {
    state.datasetStatus.value = t("status.datasetCreating");
    try {
      const result = await invoke("engine_request", {
        method: "dataset.create",
        params: {
          board_spec_path: state.boardSpecPath.value || undefined,
          out_dir: state.datasetOutDir.value || undefined,
        },
      });
      state.datasetJobId.value = result.job_id || "";
      state.datasetOutDir.value = result.out_dir || state.datasetOutDir.value;
      state.datasetStatus.value = `${t("status.submitted")}${state.datasetJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.datasetStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 向数据集添加观测数据
   */
  const runDatasetAddObservation = async () => {
    if (!state.datasetId.value) {
      toastShow(t("toast.missingDataset"), t("toast.missingDatasetDesc"));
      return;
    }
    const observationPath = state.datasetObservationPath.value || state.lutObservationPath.value;
    if (!observationPath) {
      toastShow(t("toast.missingObservation"), t("toast.missingObservationDesc"));
      return;
    }
    state.datasetStatus.value = t("status.datasetAdding");
    try {
      const result = await invoke("engine_request", {
        method: "dataset.add_observation",
        params: {
          dataset_id: state.datasetId.value,
          observation_path: observationPath,
          board_spec_path: state.boardSpecPath.value || undefined,
        },
      });
      state.datasetJobId.value = result.job_id || "";
      state.datasetStatus.value = `${t("status.submitted")}${state.datasetJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.datasetStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 聚合数据集数据
   */
  const runDatasetAggregate = async () => {
    if (!state.datasetId.value) {
      toastShow(t("toast.missingDataset"), t("toast.missingDatasetDesc"));
      return;
    }
    state.datasetStatus.value = t("status.datasetAggregating");
    try {
      const result = await invoke("engine_request", {
        method: "dataset.aggregate",
        params: {
          dataset_id: state.datasetId.value,
          out_dir: state.datasetOutDir.value || undefined,
        },
      });
      state.datasetJobId.value = result.job_id || "";
      state.datasetOutDir.value = result.out_dir || state.datasetOutDir.value;
      state.datasetStatus.value = `${t("status.submitted")}${state.datasetJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.datasetStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 运行 MCRT 验证任务
   * 使用蒙特卡洛射线追踪模拟来验证校色结果的准确性
   */
  const runMcrtValidate = async () => {
    if (!state.datasetId.value) {
      toastShow(t("toast.missingDataset"), t("toast.missingDatasetDesc"));
      return;
    }
    state.mcrtStatus.value = t("status.mcrtRunning");
    try {
      const result = await invoke("engine_request", {
        method: "dataset.mcrt_validate",
        params: {
          dataset_id: state.datasetId.value,
          observation_path: state.datasetObservationPath.value || undefined,
          board_spec_path: state.boardSpecPath.value || undefined,
          samples: Number(state.mcrtSamples.value),
          backend: state.mcrtBackend.value,
          layer_height_mm: Number(state.mcrtLayerHeight.value),
          backing_albedo: Number(state.mcrtBackingAlbedo.value),
          color_system: state.mcrtColorSystem.value,
          out_dir: state.datasetOutDir.value || undefined,
        },
      });
      state.mcrtJobId.value = result.job_id || "";
      state.mcrtStatus.value = `${t("status.submitted")}${state.mcrtJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.mcrtStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 运行位图转换与导出任务
   * 将图片转换为 3D 打印用的 STL 或 3MF 格式
   */
  const runBitmapExport = async () => {
    state.bitmapStatus.value = "";
    state.bitmapProgress.value = -1;
    state.bitmapStage.value = "";
    state.bitmapPreview2dPath.value = "";

    let standard3mfPath = undefined;
    let bambu3mfPath = undefined;

    if (state.outputFormat.value === "3mf" && state.libraryRoot.value) {
      // 如果使用了资源库，则自动分流到 Standard 和 Bambu 目录
      standard3mfPath = await joinPaths(state.libraryRoot.value, "Exports/3MF/Standard", "opencolor_standard.3mf");
      bambu3mfPath = await joinPaths(state.libraryRoot.value, "Exports/3MF/Bambu", "opencolor_bambu.3mf");
    }

    try {
      const result = await invoke("engine_request", {
        method: "bitmap.export",
        params: {
          image_path: state.bitmapImagePath.value,
          lut_path: state.bitmapLutPath.value,
          nozzle_width_mm: Number(state.bitmapNozzle.value),
          target_width_mm: Number(state.bitmapWidth.value),
          n_layers: Number(state.bitmapLayers.value),
          algo: state.bitmapAlgo.value,
          smooth_sigma: Number(state.bitmapSdfSmoothSigma.value),
          simplify_eps: Number(state.bitmapSdfSimplifyEps.value),
          auto_bg_remove: Boolean(state.bitmapAutoBgRemove.value),
          bg_tol: Number(state.bitmapBgTol.value),
          alpha_threshold: Number(state.bitmapAlphaThreshold.value),
          output_format: state.outputFormat.value,
          export_3mf_standard: state.outputFormat.value === "3mf",
          export_3mf_bambu: state.outputFormat.value === "3mf",
          standard_3mf_path: standard3mfPath,
          bambu_3mf_path: bambu3mfPath,
          out_dir: state.bitmapOutDir.value || undefined,
        },
      });
      state.bitmapJobId.value = result.job_id || "";
      state.bitmapOutDir.value = result.out_dir || state.bitmapOutDir.value;
      state.bitmapStatus.value = `${t("status.submitted")}${state.bitmapJobId.value}`;
    } catch (e) {
      const msg = `${t("status.submitFail")}${e}`;
      console.error(msg);
      state.bitmapStatus.value = msg;
      toastShow(t("status.submitFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 取消当前运行的位图导出任务
   */
  const cancelBitmapExport = async () => {
    if (!state.bitmapJobId.value) {
      return;
    }
    try {
      const result = await invoke("engine_request", {
        method: "job.cancel",
        params: {
          job_id: state.bitmapJobId.value,
        },
      });
      if (result.cancelled) {
        toastShow(t("toast.taskCancelled"), t("toast.taskCancelledDesc"));
        state.bitmapStatus.value = t("status.cancelled");
      } else {
        toastShow(t("toast.cancelFailed"), t("toast.cancelFailedDesc"));
      }
    } catch (e) {
      const msg = `${t("toast.cancelFail")}${e}`;
      console.error(msg);
      toastShow(t("toast.cancelFail"), t("toast.consoleHint"));
    }
  };

  /**
   * 通用生成逻辑 (目前主要处理 PNG 输入)
   */
  const runGenerate = async () => {
    if (state.inputKind.value !== "png") {
      toastShow(t("toast.notImplemented"), t("toast.notImplementedDesc"));
      return;
    }
    if (!state.bitmapImagePath.value) {
      state.bitmapImagePath.value = state.inputPath.value;
    }
    if (!state.bitmapImagePath.value || !state.bitmapLutPath.value) {
      toastShow(t("toast.missingInput"), t("toast.missingInputDesc"));
      return;
    }
    await runBitmapExport();
  };

  /**
   * 注册引擎事件监听器
   * 监听任务进度、完成、错误以及引擎日志
   * @param {Function} listen - Tauri 事件监听函数
   */
  const registerJobListeners = async (listen) => {
    try {
      // 监听任务进度更新
      await listen("engine://job_progress", (event) => {
        const payload = event.payload || {};
        if (payload.job_id && payload.job_id === state.bitmapJobId.value) {
          state.bitmapProgress.value = Number(payload.progress || 0);
          state.bitmapStage.value = payload.stage || "";
          state.bitmapStatus.value = payload.message || "";
        }
        if (payload.job_id && payload.job_id === state.datasetJobId.value) {
          state.datasetStatus.value = payload.message || payload.stage || "";
        }
        if (payload.job_id && payload.job_id === state.mcrtJobId.value) {
          state.mcrtStatus.value = payload.message || payload.stage || "";
        }
      });
      
      // 监听任务完成
      await listen("engine://job_done", (event) => {
        const payload = event.payload || {};
        // 处理位图导出完成
        if (payload.job_id && payload.job_id === state.bitmapJobId.value) {
          const result = payload.result || {};
          state.bitmapPreview2dPath.value = result.preview2d || "";
          if (state.bitmapPreview2dPath.value) {
            state.previewMode.value = "processed";
          }
          state.bitmapStandard3mfPath.value = result.standard_3mf || "";
          state.bitmapBambu3mfPath.value = result.bambu_3mf || "";
          state.bitmapMetaPath.value = result.meta || "";
          state.bitmapOutDir.value = result.out_dir || state.bitmapOutDir.value;
          state.bitmapProgress.value = 1;
          state.bitmapStage.value = t("status.done");
          state.bitmapStatus.value = t("status.completed");
          toastShow(t("toast.bitmapDone"), state.bitmapOutDir.value || "");
        }
        // 处理 LUT 相关任务完成
        console.log("[引擎] job_done 事件:", payload.job_id, "LUT JobId:", state.lutJobId?.value);
        if (payload.job_id && payload.job_id === state.lutJobId?.value) {
          console.log("[引擎] LUT 任务完成匹配成功");
          const result = payload.result || {};
          
          if (result.overlay) {
            state.lutOverlayPath.value = result.overlay;
          }
          if (result.warped) {
            state.lutWarpedPath.value = result.warped;
          }

          if (result.lut) {
            state.lutResultSummary.value = t("status.lutGenerated");
            state.lutResultFile.value = result.lut;
            state.lutStatus.value = t("status.completed");
            toastShow(t("toast.lutDone"), result.lut);
          }
          
          if (result.grid_shape) {
            state.gridRows.value = Number(result.grid_shape.rows || 0);
            state.gridCols.value = Number(result.grid_shape.cols || 0);
            state.gridDataRows.value = Number(result.grid_shape.data_rows || 0);
            state.gridDataCols.value = Number(result.grid_shape.data_cols || 0);
            state.gridBorder.value = Number(result.grid_shape.border || 0);
          }
          if (result.observation) {
            state.lutObservationPath.value = result.observation;
            if (!state.datasetObservationPath.value) {
              state.datasetObservationPath.value = result.observation;
            }
          }
          if (result.board_spec) {
            state.boardSpecId.value = result.board_spec.board_id || "";
            state.boardSpecName.value = result.board_spec.name || "";
            state.boardSpecRows.value = Number(result.board_spec.rows || 0);
            state.boardSpecCols.value = Number(result.board_spec.cols || 0);
          }

          if (result.corner_points) {
            state.lutCornerPoints.value = JSON.stringify(result.corner_points);
            state.lutStatus.value = t("status.detectDone");
            toastShow(t("toast.detectDone"), t("toast.detectDoneDesc"));
          }
          const hasBoardStls = Array.isArray(result.stls) ? result.stls.length > 0 : Boolean(result.stls);
          const hasBoard3mf = Boolean(result.standard_3mf);
          const hasBoardSpecPath = Boolean(result.board_spec_path);
          if (hasBoard3mf || hasBoardStls || hasBoardSpecPath) {
            state.lutStatus.value = t("status.boardDone");
            toastShow(t("toast.boardDone"), result.standard_3mf || result.out_dir || "");
            // 使用消息队列触发相册刷新
            console.log("[引擎] 添加相册刷新消息 (board.generate 完成)");
            enqueueMessage('album-refresh', {
              source: 'board.generate',
              out_dir: result.out_dir,
              standard_3mf: result.standard_3mf,
              stls: result.stls,
              board_spec_path: result.board_spec_path,
              preview: result.preview,
              meta: result.meta,
            });
          }
          if (result.stl) {
            state.lutStatus.value = t("status.cardDone");
            toastShow(t("toast.cardDone"), result.stl);
            // 使用消息队列触发相册刷新
            console.log("[引擎] 添加相册刷新消息 (card.generate 完成)");
            enqueueMessage('album-refresh', { source: 'card.generate', stl: result.stl });
          }
        }
        // 处理数据集任务完成
        if (payload.job_id && payload.job_id === state.datasetJobId.value) {
          const result = payload.result || {};
          if (result.dataset_id) {
            state.datasetId.value = result.dataset_id;
          }
          if (result.out_dir) {
            state.datasetOutDir.value = result.out_dir || state.datasetOutDir.value;
          }
          if (typeof result.observation_count === "number") {
            state.datasetObsCount.value = result.observation_count;
          }
          if (typeof result.board_count === "number") {
            state.datasetBoardCount.value = result.board_count;
          }
          if (result.summary_path) {
            state.datasetSummaryPath.value = result.summary_path;
          }
          state.datasetStatus.value = t("status.completed");
          if (result.summary_path) {
            toastShow(t("toast.datasetAggregated"), result.summary_path || "");
          } else if (typeof result.observation_count === "number") {
            toastShow(t("toast.datasetObservationAdded"), `${result.observation_count}`);
          } else if (result.dataset_id) {
            toastShow(t("toast.datasetCreated"), result.dataset_id || "");
          }
        }
        // 处理 MCRT 验证完成
        if (payload.job_id && payload.job_id === state.mcrtJobId.value) {
          const result = payload.result || {};
          const avg = typeof result.avg_error === "number" ? result.avg_error.toFixed(4) : "";
          state.mcrtAvgError.value = avg;
          state.mcrtDiagnosticsPath.value = result.diagnostics_path || "";
          state.mcrtDiagnostics.value = result.diagnostics || {};
          state.mcrtStatus.value = t("status.completed");
          toastShow(t("toast.mcrtDone"), avg || "");
        }
      });

      // 监听任务错误
      await listen("engine://job_error", (event) => {
        const payload = event.payload || {};
        const msg = payload.message || t("toast.jobFail");
        console.error(t("toast.jobFail"), payload);
        if (payload.job_id && payload.job_id === state.bitmapJobId.value) {
          state.bitmapStatus.value = msg;
        }
        if (payload.job_id && payload.job_id === state.lutJobId.value) {
          state.lutStatus.value = msg;
        }
        if (payload.job_id && payload.job_id === state.datasetJobId.value) {
          state.datasetStatus.value = msg;
        }
        if (payload.job_id && payload.job_id === state.mcrtJobId.value) {
          state.mcrtStatus.value = msg;
        }
        toastShow(t("toast.taskFail"), msg);
      });

      // 监听引擎常规日志
      await listen("engine://log", (event) => {
        const payload = event.payload || {};
        const msg = payload.message || "";
        if (msg) console.log(t("status.engineLog"), msg);
      });
    } catch (e) {
      console.error("注册引擎事件失败", e);
    }
  };

  return {
    pingEngine,
    runLutExtract,
    runLutDetect,
    runBoardGenerate,
    runQuickCalibCardGenerate,
    runDatasetCreate,
    runDatasetAddObservation,
    runDatasetAggregate,
    runMcrtValidate,
    runBitmapExport,
    cancelBitmapExport,
    runGenerate,
    registerJobListeners,
  };
};
