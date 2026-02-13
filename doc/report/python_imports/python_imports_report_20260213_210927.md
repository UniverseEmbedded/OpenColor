# Python 引用关系分析报告

## 摘要

| 指标 | 数值 |
|------|------|
| 总文件数 | 167 |
| 孤立文件数 | 28 |
| 循环依赖数 | 2 |
| 入口模块可达文件数 | 134 |
| 其他文件数 | 33 |

## 孤立文件（未被引用）

以下文件没有被其他模块导入，也不是入口点（没有 `__main__` 块）：

- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\test_board_preview.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\opencolor\src\oc_core_02\core\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\calibration\src\oc_calib\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\test_api_bridge_board.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\opencolor\src\oc_core_02\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\errors.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\handlers\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\conftest.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\test_api_bridge_ping.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\svg\svg_mesh_verify_geom.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\engine\src\oc_engine\tests\test_bitmap_export_3mf.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\xgb\src\oc_xgb\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\stl\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\calib_color_rts\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\calib_photo_warp\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\calib_sample_build\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\common\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\gen_3mf\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\sdf\src\oc_sdf\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\calibration\color_board\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\prototypes\src\oc_proto\gen_vector\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\calibration\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\calibration\multicolor\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\calibration\utils\__init__.py`
- `D:\pama1234\pfp\p-2026-01\OpenColor-05\py_module\scripts\src\oc_scripts\planning\planner_search.py`

## 入口点文件

以下文件包含 `if __name__ == "__main__"` 块，可以作为程序入口：

- `oc_analyze.scan_dense_dirs` (py_module\analyze\src\oc_analyze\scan_dense_dirs.py)
- `oc_analyze.package_project` (py_module\analyze\src\oc_analyze\package_project.py)
- `oc_analyze.replace_print` (py_module\analyze\src\oc_analyze\replace_print.py)
- `oc_analyze.scan_comment` (py_module\analyze\src\oc_analyze\scan_comment.py)
- `oc_analyze.scan_duplicate` (py_module\analyze\src\oc_analyze\scan_duplicate.py)
- `oc_analyze.scan_large_files` (py_module\analyze\src\oc_analyze\scan_large_files.py)
- `oc_analyze.scan_python_imports` (py_module\analyze\src\oc_analyze\scan_python_imports.py)
- `oc_analyze.scan_long_filenames` (py_module\analyze\src\oc_analyze\scan_long_filenames.py)
- `oc_analyze.scan_ruff` (py_module\analyze\src\oc_analyze\scan_ruff.py)
- `oc_analyze.sync_to_repo` (py_module\analyze\src\oc_analyze\sync_to_repo.py)
- `oc_proto.calib_board_gen.main` (py_module\prototypes\src\oc_proto\calib_board_gen\main.py)
- `oc_proto.calib_photo_warp.app` (py_module\prototypes\src\oc_proto\calib_photo_warp\app.py)
- `oc_engine.main` (py_module\engine\src\oc_engine\main.py)
- `oc_core_02.utils.clean` (py_module\opencolor\src\oc_core_02\utils\clean.py)
- `oc_core_02.app` (py_module\opencolor\src\oc_core_02\app.py)
- `oc_proto.gen_masks.dot_pattern_test` (py_module\prototypes\src\oc_proto\gen_masks\dot_pattern_test.py)
- `oc_proto.calib_board_gen.color_contact_3mf` (py_module\prototypes\src\oc_proto\calib_board_gen\color_contact_3mf.py)
- `oc_proto.calib_board_gen.generate_board` (py_module\prototypes\src\oc_proto\calib_board_gen\generate_board.py)
- `oc_proto.calib_board_gen.interactive_gen` (py_module\prototypes\src\oc_proto\calib_board_gen\interactive_gen.py)
- `oc_proto.calib_color_rts.eval_comparison_all` (py_module\prototypes\src\oc_proto\calib_color_rts\eval_comparison_all.py)
- `oc_proto.calib_color_rts.main` (py_module\prototypes\src\oc_proto\calib_color_rts\main.py)
- `oc_proto.calib_color_rts.model_physics_visualizer` (py_module\prototypes\src\oc_proto\calib_color_rts\model_physics_visualizer.py)
- `oc_proto.calib_color_rts.models.new_model_template` (py_module\prototypes\src\oc_proto\calib_color_rts\models\new_model_template.py)
- `oc_proto.calib_color_rts.od_eval_fullpairs` (py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_fullpairs.py)
- `oc_proto.calib_color_rts.od_eval_logit_pairs` (py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_logit_pairs.py)
- `oc_proto.calib_color_rts.od_eval_runner` (py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_runner.py)
- `oc_proto.calib_color_rts.rt_stack_fit_eval` (py_module\prototypes\src\oc_proto\calib_color_rts\rt_stack_fit_eval.py)
- `oc_proto.calib_sample_build.main` (py_module\prototypes\src\oc_proto\calib_sample_build\main.py)
- `oc_proto.gen_3mf.batch_process` (py_module\prototypes\src\oc_proto\gen_3mf\batch_process.py)
- `oc_proto.gen_3mf.evidence_rebuild` (py_module\prototypes\src\oc_proto\gen_3mf\evidence_rebuild.py)
- `oc_proto.gen_3mf.main` (py_module\prototypes\src\oc_proto\gen_3mf\main.py)
- `oc_proto.gen_masks.batch_process` (py_module\prototypes\src\oc_proto\gen_masks\batch_process.py)
- `oc_proto.gen_masks.diagnose_all_pure_colors` (py_module\prototypes\src\oc_proto\gen_masks\diagnose_all_pure_colors.py)
- `oc_proto.gen_masks.gray_test` (py_module\prototypes\src\oc_proto\gen_masks\gray_test.py)
- `oc_proto.gen_masks.main` (py_module\prototypes\src\oc_proto\gen_masks\main.py)
- `oc_proto.gen_masks.solver_cpp_wrapper` (py_module\prototypes\src\oc_proto\gen_masks\solver_cpp_wrapper.py)
- `oc_proto.gen_vector.batch_process` (py_module\prototypes\src\oc_proto\gen_vector\batch_process.py)
- `oc_proto.gen_vector.main` (py_module\prototypes\src\oc_proto\gen_vector\main.py)
- `oc_proto.gen_vector.mask_overlap_check` (py_module\prototypes\src\oc_proto\gen_vector\mask_overlap_check.py)

## 循环依赖

- `oc_core_02.utils.vtracer_bridge` -> `oc_sdf.sdf_utils`
- `oc_sdf.sdf_utils` -> `oc_core_02.utils.vtracer_bridge`

## 第一组：入口模块及其依赖

从指定的入口模块开始，递归收集的所有可达文件（包括入口模块本身及其导入的所有模块）。

| 模块名 | 路径 | 行数 | 导入数 | 被引用数 |
|--------|------|------|--------|----------|
| `model_export` | py_module\model_export\src\model_export\__init__.py | 23 | 2 | 1 |
| `model_export.atomic_io` | py_module\model_export\src\model_export\atomic_io.py | 88 | 5 | 1 |
| `model_export.mesh_utils` | py_module\model_export\src\model_export\mesh_utils.py | 356 | 8 | 2 |
| `model_export.standard_3mf` | py_module\model_export\src\model_export\standard_3mf.py | 531 | 12 | 5 |
| `model_export.types` | py_module\model_export\src\model_export\types.py | 123 | 3 | 4 |
| `oc_analyze.package_project` | py_module\analyze\src\oc_analyze\package_project.py | 641 | 10 | 0 |
| `oc_analyze.replace_print` | py_module\analyze\src\oc_analyze\replace_print.py | 365 | 4 | 0 |
| `oc_analyze.scan_comment` | py_module\analyze\src\oc_analyze\scan_comment.py | 314 | 9 | 0 |
| `oc_analyze.scan_dense_dirs` | py_module\analyze\src\oc_analyze\scan_dense_dirs.py | 353 | 8 | 0 |
| `oc_analyze.scan_duplicate` | py_module\analyze\src\oc_analyze\scan_duplicate.py | 922 | 13 | 0 |
| `oc_analyze.scan_large_files` | py_module\analyze\src\oc_analyze\scan_large_files.py | 305 | 7 | 0 |
| `oc_analyze.scan_long_filenames` | py_module\analyze\src\oc_analyze\scan_long_filenames.py | 482 | 7 | 0 |
| `oc_analyze.scan_python_imports` | py_module\analyze\src\oc_analyze\scan_python_imports.py | 285 | 7 | 0 |
| `oc_analyze.scan_ruff` | py_module\analyze\src\oc_analyze\scan_ruff.py | 654 | 9 | 0 |
| `oc_analyze.scan_utils` | py_module\analyze\src\oc_analyze\scan_utils.py | 125 | 4 | 5 |
| `oc_analyze.sync_to_repo` | py_module\analyze\src\oc_analyze\sync_to_repo.py | 388 | 7 | 0 |
| `oc_calib.aggregate` | py_module\calibration\src\oc_calib\aggregate.py | 48 | 3 | 2 |
| `oc_calib.board` | py_module\calibration\src\oc_calib\board.py | 630 | 12 | 2 |
| `oc_calib.board_spec` | py_module\calibration\src\oc_calib\board_spec.py | 102 | 6 | 10 |
| `oc_calib.calibration` | py_module\calibration\src\oc_calib\calibration.py | 259 | 4 | 3 |
| `oc_calib.dataset` | py_module\calibration\src\oc_calib\dataset.py | 65 | 7 | 4 |
| `oc_calib.observation` | py_module\calibration\src\oc_calib\observation.py | 43 | 4 | 4 |
| `oc_calib.spec_adapter` | py_module\calibration\src\oc_calib\spec_adapter.py | 401 | 4 | 3 |
| `oc_core_02.app` | py_module\opencolor\src\oc_core_02\app.py | 75 | 7 | 0 |
| `oc_core_02.core.app_paths` | py_module\opencolor\src\oc_core_02\core\app_paths.py | 120 | 6 | 5 |
| `oc_core_02.core.bitmap_pipeline` | py_module\opencolor\src\oc_core_02\core\bitmap_pipeline.py | 352 | 13 | 9 |
| `oc_core_02.core.bitmap_pipeline_sdf` | py_module\opencolor\src\oc_core_02\core\bitmap_pipeline_sdf.py | 227 | 19 | 2 |
| `oc_core_02.core.color_systems` | py_module\opencolor\src\oc_core_02\core\color_systems.py | 141 | 2 | 18 |
| `oc_core_02.core.mesh_export` | py_module\opencolor\src\oc_core_02\core\mesh_export.py | 333 | 9 | 6 |
| `oc_core_02.core.model_analysis` | py_module\opencolor\src\oc_core_02\core\model_analysis.py | 292 | 9 | 4 |
| `oc_core_02.core.recipes` | py_module\opencolor\src\oc_core_02\core\recipes.py | 58 | 2 | 2 |
| `oc_core_02.core.svg_processing` | py_module\opencolor\src\oc_core_02\core\svg_processing.py | 463 | 10 | 1 |
| `oc_core_02.core.three_mf` | py_module\opencolor\src\oc_core_02\core\three_mf.py | 169 | 5 | 2 |
| `oc_core_02.ui.bitmap` | py_module\opencolor\src\oc_core_02\ui\bitmap.py | 162 | 7 | 1 |
| `oc_core_02.ui.board` | py_module\opencolor\src\oc_core_02\ui\board.py | 51 | 4 | 1 |
| `oc_core_02.ui.calibration` | py_module\opencolor\src\oc_core_02\ui\calibration.py | 674 | 17 | 1 |
| `oc_core_02.ui.dataset` | py_module\opencolor\src\oc_core_02\ui\dataset.py | 49 | 6 | 1 |
| `oc_core_02.ui.utils` | py_module\opencolor\src\oc_core_02\ui\utils.py | 113 | 7 | 4 |
| `oc_core_02.utils` | py_module\opencolor\src\oc_core_02\utils\__init__.py | 9 | 1 | 1 |
| `oc_core_02.utils.bin_loader` | py_module\opencolor\src\oc_core_02\utils\bin_loader.py | 98 | 6 | 13 |
| `oc_core_02.utils.clean` | py_module\opencolor\src\oc_core_02\utils\clean.py | 93 | 4 | 0 |
| `oc_core_02.utils.io_utils` | py_module\opencolor\src\oc_core_02\utils\io_utils.py | 90 | 9 | 6 |
| `oc_core_02.utils.logger` | py_module\opencolor\src\oc_core_02\utils\logger.py | 109 | 4 | 93 |
| `oc_core_02.utils.manifest` | py_module\opencolor\src\oc_core_02\utils\manifest.py | 44 | 4 | 5 |
| `oc_core_02.utils.paths` | py_module\opencolor\src\oc_core_02\utils\paths.py | 121 | 4 | 8 |
| `oc_core_02.utils.vtracer_bridge` | py_module\opencolor\src\oc_core_02\utils\vtracer_bridge.py | 987 | 22 | 4 |
| `oc_engine.api_bridge` | py_module\engine\src\oc_engine\api_bridge.py | 331 | 17 | 2 |
| `oc_engine.handlers.bitmap` | py_module\engine\src\oc_engine\handlers\bitmap.py | 263 | 13 | 3 |
| `oc_engine.handlers.board` | py_module\engine\src\oc_engine\handlers\board.py | 956 | 19 | 3 |
| `oc_engine.handlers.dataset` | py_module\engine\src\oc_engine\handlers\dataset.py | 216 | 9 | 2 |
| `oc_engine.handlers.health` | py_module\engine\src\oc_engine\handlers\health.py | 29 | 1 | 2 |
| `oc_engine.handlers.lut` | py_module\engine\src\oc_engine\handlers\lut.py | 246 | 11 | 2 |
| `oc_engine.handlers.svg` | py_module\engine\src\oc_engine\handlers\svg.py | 306 | 10 | 2 |
| `oc_engine.jobs` | py_module\engine\src\oc_engine\jobs.py | 109 | 7 | 8 |
| `oc_engine.main` | py_module\engine\src\oc_engine\main.py | 189 | 15 | 0 |
| `oc_engine.protocol` | py_module\engine\src\oc_engine\protocol.py | 114 | 3 | 3 |
| `oc_engine.schema` | py_module\engine\src\oc_engine\schema.py | 176 | 2 | 2 |
| `oc_proto` | py_module\prototypes\src\oc_proto\__init__.py | 2 | 0 | 1 |
| `oc_proto.calib_board_gen` | py_module\prototypes\src\oc_proto\calib_board_gen\__init__.py | 2 | 0 | 3 |
| `oc_proto.calib_board_gen.color_contact_3mf` | py_module\prototypes\src\oc_proto\calib_board_gen\color_contact_3mf.py | 537 | 17 | 0 |
| `oc_proto.calib_board_gen.color_profiles` | py_module\prototypes\src\oc_proto\calib_board_gen\color_profiles.py | 371 | 3 | 4 |
| `oc_proto.calib_board_gen.generate_board` | py_module\prototypes\src\oc_proto\calib_board_gen\generate_board.py | 915 | 14 | 0 |
| `oc_proto.calib_board_gen.interactive_gen` | py_module\prototypes\src\oc_proto\calib_board_gen\interactive_gen.py | 365 | 8 | 0 |
| `oc_proto.calib_board_gen.main` | py_module\prototypes\src\oc_proto\calib_board_gen\main.py | 355 | 10 | 1 |
| `oc_proto.calib_color_rts.cli` | py_module\prototypes\src\oc_proto\calib_color_rts\cli.py | 422 | 12 | 3 |
| `oc_proto.calib_color_rts.dataset_io` | py_module\prototypes\src\oc_proto\calib_color_rts\dataset_io.py | 235 | 5 | 4 |
| `oc_proto.calib_color_rts.diagnostics` | py_module\prototypes\src\oc_proto\calib_color_rts\diagnostics.py | 463 | 7 | 3 |
| `oc_proto.calib_color_rts.eval_comparison_all` | py_module\prototypes\src\oc_proto\calib_color_rts\eval_comparison_all.py | 669 | 11 | 0 |
| `oc_proto.calib_color_rts.main` | py_module\prototypes\src\oc_proto\calib_color_rts\main.py | 994 | 17 | 0 |
| `oc_proto.calib_color_rts.model_physics_visualizer` | py_module\prototypes\src\oc_proto\calib_color_rts\model_physics_visualizer.py | 728 | 10 | 0 |
| `oc_proto.calib_color_rts.models.ml_residual_model` | py_module\prototypes\src\oc_proto\calib_color_rts\models\ml_residual_model.py | 164 | 8 | 3 |
| `oc_proto.calib_color_rts.models.new_model_template` | py_module\prototypes\src\oc_proto\calib_color_rts\models\new_model_template.py | 222 | 5 | 0 |
| `oc_proto.calib_color_rts.od_eval_fullpairs` | py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_fullpairs.py | 191 | 4 | 0 |
| `oc_proto.calib_color_rts.od_eval_logit_pairs` | py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_logit_pairs.py | 193 | 4 | 0 |
| `oc_proto.calib_color_rts.od_eval_runner` | py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_runner.py | 257 | 4 | 0 |
| `oc_proto.calib_color_rts.rt_stack_fit_eval` | py_module\prototypes\src\oc_proto\calib_color_rts\rt_stack_fit_eval.py | 505 | 9 | 0 |
| `oc_proto.calib_color_rts.runner` | py_module\prototypes\src\oc_proto\calib_color_rts\runner.py | 574 | 13 | 1 |
| `oc_proto.calib_photo_warp.app` | py_module\prototypes\src\oc_proto\calib_photo_warp\app.py | 706 | 18 | 0 |
| `oc_proto.calib_sample_build.main` | py_module\prototypes\src\oc_proto\calib_sample_build\main.py | 1036 | 12 | 0 |
| `oc_proto.gen_3mf.batch_process` | py_module\prototypes\src\oc_proto\gen_3mf\batch_process.py | 96 | 4 | 0 |
| `oc_proto.gen_3mf.evidence_rebuild` | py_module\prototypes\src\oc_proto\gen_3mf\evidence_rebuild.py | 303 | 11 | 0 |
| `oc_proto.gen_3mf.geometry_bridge` | py_module\prototypes\src\oc_proto\gen_3mf\geometry_bridge.py | 161 | 4 | 2 |
| `oc_proto.gen_3mf.interrupt_handler` | py_module\prototypes\src\oc_proto\gen_3mf\interrupt_handler.py | 70 | 5 | 2 |
| `oc_proto.gen_3mf.main` | py_module\prototypes\src\oc_proto\gen_3mf\main.py | 497 | 24 | 2 |
| `oc_proto.gen_masks` | py_module\prototypes\src\oc_proto\gen_masks\__init__.py | 114 | 7 | 2 |
| `oc_proto.gen_masks.batch_process` | py_module\prototypes\src\oc_proto\gen_masks\batch_process.py | 91 | 6 | 0 |
| `oc_proto.gen_masks.diagnose_all_pure_colors` | py_module\prototypes\src\oc_proto\gen_masks\diagnose_all_pure_colors.py | 181 | 6 | 0 |
| `oc_proto.gen_masks.dot_pattern_test` | py_module\prototypes\src\oc_proto\gen_masks\dot_pattern_test.py | 797 | 17 | 0 |
| `oc_proto.gen_masks.filters` | py_module\prototypes\src\oc_proto\gen_masks\filters.py | 134 | 3 | 3 |
| `oc_proto.gen_masks.gray_test` | py_module\prototypes\src\oc_proto\gen_masks\gray_test.py | 327 | 16 | 0 |
| `oc_proto.gen_masks.island_suppress` | py_module\prototypes\src\oc_proto\gen_masks\island_suppress.py | 414 | 7 | 2 |
| `oc_proto.gen_masks.joint_refinement` | py_module\prototypes\src\oc_proto\gen_masks\joint_refinement.py | 1011 | 10 | 2 |
| `oc_proto.gen_masks.joint_refinement_boundary` | py_module\prototypes\src\oc_proto\gen_masks\joint_refinement_boundary.py | 189 | 3 | 5 |
| `oc_proto.gen_masks.joint_refinement_cleanup` | py_module\prototypes\src\oc_proto\gen_masks\joint_refinement_cleanup.py | 184 | 2 | 4 |
| `oc_proto.gen_masks.joint_refinement_filter` | py_module\prototypes\src\oc_proto\gen_masks\joint_refinement_filter.py | 94 | 6 | 2 |
| `oc_proto.gen_masks.joint_refinement_icm` | py_module\prototypes\src\oc_proto\gen_masks\joint_refinement_icm.py | 928 | 10 | 2 |
| `oc_proto.gen_masks.main` | py_module\prototypes\src\oc_proto\gen_masks\main.py | 374 | 6 | 2 |
| `oc_proto.gen_masks.main_preprocess` | py_module\prototypes\src\oc_proto\gen_masks\main_preprocess.py | 286 | 16 | 1 |
| `oc_proto.gen_masks.main_runner` | py_module\prototypes\src\oc_proto\gen_masks\main_runner.py | 859 | 22 | 1 |
| `oc_proto.gen_masks.main_solve` | py_module\prototypes\src\oc_proto\gen_masks\main_solve.py | 314 | 14 | 1 |
| `oc_proto.gen_masks.main_utils` | py_module\prototypes\src\oc_proto\gen_masks\main_utils.py | 66 | 4 | 3 |
| `oc_proto.gen_masks.optimizer` | py_module\prototypes\src\oc_proto\gen_masks\optimizer.py | 224 | 5 | 3 |
| `oc_proto.gen_masks.solver` | py_module\prototypes\src\oc_proto\gen_masks\solver.py | 308 | 8 | 1 |
| `oc_proto.gen_masks.solver_cpp_wrapper` | py_module\prototypes\src\oc_proto\gen_masks\solver_cpp_wrapper.py | 203 | 4 | 3 |
| `oc_proto.gen_masks.stats` | py_module\prototypes\src\oc_proto\gen_masks\stats.py | 191 | 5 | 3 |
| `oc_proto.gen_masks.visualization` | py_module\prototypes\src\oc_proto\gen_masks\visualization.py | 271 | 5 | 2 |
| `oc_proto.gen_vector.batch_process` | py_module\prototypes\src\oc_proto\gen_vector\batch_process.py | 96 | 6 | 0 |
| `oc_proto.gen_vector.exclusive_clipper` | py_module\prototypes\src\oc_proto\gen_vector\exclusive_clipper.py | 245 | 10 | 2 |
| `oc_proto.gen_vector.main` | py_module\prototypes\src\oc_proto\gen_vector\main.py | 1092 | 30 | 1 |
| `oc_proto.gen_vector.mask_overlap_check` | py_module\prototypes\src\oc_proto\gen_vector\mask_overlap_check.py | 304 | 7 | 1 |
| `oc_proto.gen_vector.reconcile` | py_module\prototypes\src\oc_proto\gen_vector\reconcile.py | 177 | 8 | 1 |
| `oc_proto.gen_vector.resampler` | py_module\prototypes\src\oc_proto\gen_vector\resampler.py | 358 | 11 | 1 |
| `oc_proto.gen_vector.svg_utils` | py_module\prototypes\src\oc_proto\gen_vector\svg_utils.py | 119 | 0 | 1 |
| `oc_proto.gen_vector.visualization` | py_module\prototypes\src\oc_proto\gen_vector\visualization.py | 220 | 7 | 1 |
| `oc_proto.gen_vector.workers` | py_module\prototypes\src\oc_proto\gen_vector\workers.py | 157 | 10 | 1 |
| `oc_scripts.calibration.calibrate_color_board_io` | py_module\scripts\src\oc_scripts\calibration\calibrate_color_board_io.py | 57 | 3 | 1 |
| `oc_scripts.calibration.color_board.calib_geom` | py_module\scripts\src\oc_scripts\calibration\color_board\calib_geom.py | 146 | 5 | 2 |
| `oc_sdf.geometry_utils` | py_module\sdf\src\oc_sdf\geometry_utils.py | 471 | 6 | 2 |
| `oc_sdf.sdf_data_prep` | py_module\sdf\src\oc_sdf\sdf_data_prep.py | 139 | 6 | 3 |
| `oc_sdf.sdf_export` | py_module\sdf\src\oc_sdf\sdf_export.py | 304 | 12 | 2 |
| `oc_sdf.sdf_extrude` | py_module\sdf\src\oc_sdf\sdf_extrude.py | 791 | 13 | 2 |
| `oc_sdf.sdf_io` | py_module\sdf\src\oc_sdf\sdf_io.py | 435 | 10 | 8 |
| `oc_sdf.sdf_mesh` | py_module\sdf\src\oc_sdf\sdf_mesh.py | 188 | 6 | 2 |
| `oc_sdf.sdf_polygon_gen` | py_module\sdf\src\oc_sdf\sdf_polygon_gen.py | 221 | 10 | 1 |
| `oc_sdf.sdf_quality` | py_module\sdf\src\oc_sdf\sdf_quality.py | 182 | 12 | 1 |
| `oc_sdf.sdf_types` | py_module\sdf\src\oc_sdf\sdf_types.py | 42 | 1 | 3 |
| `oc_sdf.sdf_utils` | py_module\sdf\src\oc_sdf\sdf_utils.py | 636 | 18 | 3 |
| `oc_xgb.color_space` | py_module\xgb\src\oc_xgb\color_space.py | 67 | 2 | 14 |
| `oc_xgb.model_base` | py_module\xgb\src\oc_xgb\model_base.py | 224 | 6 | 5 |
| `oc_xgb.model_io` | py_module\xgb\src\oc_xgb\model_io.py | 306 | 7 | 5 |
| `oc_xgb.optical_model` | py_module\xgb\src\oc_xgb\optical_model.py | 449 | 7 | 2 |
| `oc_xgb.xgb_features` | py_module\xgb\src\oc_xgb\xgb_features.py | 280 | 2 | 5 |
| `oc_xgb.xgb_fit` | py_module\xgb\src\oc_xgb\xgb_fit.py | 611 | 9 | 8 |
| `oc_xgb.xgb_model` | py_module\xgb\src\oc_xgb\xgb_model.py | 134 | 4 | 2 |

## 第二组：其他文件

未被入口模块直接或间接引用的文件。

| 模块名 | 路径 | 行数 | 导入数 | 被引用数 |
|--------|------|------|--------|----------|
| `oc_calib` | py_module\calibration\src\oc_calib\__init__.py | 1 | 0 | 0 |
| `oc_core_02` | py_module\opencolor\src\oc_core_02\__init__.py | 2 | 0 | 0 |
| `oc_core_02.core` | py_module\opencolor\src\oc_core_02\core\__init__.py | 2 | 0 | 0 |
| `oc_engine` | py_module\engine\src\oc_engine\__init__.py | 2 | 0 | 0 |
| `oc_engine.errors` | py_module\engine\src\oc_engine\errors.py | 186 | 10 | 0 |
| `oc_engine.handlers` | py_module\engine\src\oc_engine\handlers\__init__.py | 196 | 6 | 0 |
| `oc_engine.tests` | py_module\engine\src\oc_engine\tests\__init__.py | 3 | 0 | 0 |
| `oc_engine.tests.conftest` | py_module\engine\src\oc_engine\tests\conftest.py | 86 | 4 | 0 |
| `oc_engine.tests.test_api_bridge_board` | py_module\engine\src\oc_engine\tests\test_api_bridge_board.py | 439 | 6 | 0 |
| `oc_engine.tests.test_api_bridge_ping` | py_module\engine\src\oc_engine\tests\test_api_bridge_ping.py | 217 | 7 | 0 |
| `oc_engine.tests.test_bitmap_export_3mf` | py_module\engine\src\oc_engine\tests\test_bitmap_export_3mf.py | 174 | 9 | 0 |
| `oc_engine.tests.test_board_preview` | py_module\engine\src\oc_engine\tests\test_board_preview.py | 335 | 5 | 0 |
| `oc_proto.calib_color_rts` | py_module\prototypes\src\oc_proto\calib_color_rts\__init__.py | 66 | 5 | 0 |
| `oc_proto.calib_color_rts.models` | py_module\prototypes\src\oc_proto\calib_color_rts\models\__init__.py | 23 | 2 | 1 |
| `oc_proto.calib_color_rts.models.phys_gpr_model` | py_module\prototypes\src\oc_proto\calib_color_rts\models\phys_gpr_model.py | 312 | 8 | 1 |
| `oc_proto.calib_photo_warp` | py_module\prototypes\src\oc_proto\calib_photo_warp\__init__.py | 2 | 0 | 0 |
| `oc_proto.calib_sample_build` | py_module\prototypes\src\oc_proto\calib_sample_build\__init__.py | 2 | 0 | 0 |
| `oc_proto.common` | py_module\prototypes\src\oc_proto\common\__init__.py | 2 | 0 | 0 |
| `oc_proto.gen_3mf` | py_module\prototypes\src\oc_proto\gen_3mf\__init__.py | 48 | 5 | 0 |
| `oc_proto.gen_3mf.voxel_repair` | py_module\prototypes\src\oc_proto\gen_3mf\voxel_repair.py | 86 | 7 | 1 |
| `oc_proto.gen_vector` | py_module\prototypes\src\oc_proto\gen_vector\__init__.py | 2 | 0 | 0 |
| `oc_scripts` | py_module\scripts\src\oc_scripts\__init__.py | 1 | 0 | 0 |
| `oc_scripts.calibration` | py_module\scripts\src\oc_scripts\calibration\__init__.py | 2 | 0 | 0 |
| `oc_scripts.calibration.color_board` | py_module\scripts\src\oc_scripts\calibration\color_board\__init__.py | 2 | 0 | 0 |
| `oc_scripts.calibration.multicolor` | py_module\scripts\src\oc_scripts\calibration\multicolor\__init__.py | 2 | 0 | 0 |
| `oc_scripts.calibration.utils` | py_module\scripts\src\oc_scripts\calibration\utils\__init__.py | 2 | 0 | 0 |
| `oc_scripts.planning.planner_io` | py_module\scripts\src\oc_scripts\planning\planner_io.py | 170 | 5 | 1 |
| `oc_scripts.planning.planner_models` | py_module\scripts\src\oc_scripts\planning\planner_models.py | 214 | 3 | 2 |
| `oc_scripts.planning.planner_search` | py_module\scripts\src\oc_scripts\planning\planner_search.py | 311 | 5 | 0 |
| `oc_scripts.stl` | py_module\scripts\src\oc_scripts\stl\__init__.py | 2 | 0 | 0 |
| `oc_scripts.svg.svg_mesh_verify_geom` | py_module\scripts\src\oc_scripts\svg\svg_mesh_verify_geom.py | 547 | 10 | 0 |
| `oc_sdf` | py_module\sdf\src\oc_sdf\__init__.py | 1 | 0 | 0 |
| `oc_xgb` | py_module\xgb\src\oc_xgb\__init__.py | 1 | 0 | 0 |

