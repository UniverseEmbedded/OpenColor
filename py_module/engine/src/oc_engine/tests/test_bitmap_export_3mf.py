from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from oc_engine.handlers.bitmap import handle_bitmap_export
from oc_engine.jobs import Job


def _make_demo_lut(path: Path) -> None:
    """生成演示用的查找表（LUT）

    创建一个32x32的LUT，包含1024个RGB颜色值
    颜色值通过递增计算生成，用于测试位图导出功能

    Args:
        path: LUT文件的保存路径
    """
    # 32x32 LUT => 1024 RGB rows
    lut = np.zeros((32, 32, 3), dtype=np.float32)
    k = 0
    for y in range(32):
        for x in range(32):
            lut[y, x, 0] = (k * 17) % 256
            lut[y, x, 1] = (k * 29) % 256
            lut[y, x, 2] = (k * 43) % 256
            k += 1
    np.save(path, lut)


def _make_demo_image(path: Path, lut_path: Path) -> None:
    """生成演示用的测试图像

    从LUT中选择几个确定性的颜色创建调色板，
    生成一个16x16的RGBA图像，用于测试位图导出功能

    Args:
        path: 图像文件的保存路径
        lut_path: LUT文件的路径
    """
    lut = np.load(lut_path)
    # 从LUT中选择几个确定性的颜色，确保最近邻查找是可预测的
    palette = [tuple(lut[0, 0].astype(np.uint8)), tuple(lut[0, 1].astype(np.uint8)), tuple(lut[1, 0].astype(np.uint8))]
    img = np.zeros((16, 16, 4), dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            c = palette[(x + y) % len(palette)]
            img[y, x, :3] = np.array(c, dtype=np.uint8)
            img[y, x, 3] = 255
    Image.fromarray(img, mode="RGBA").save(path)


def test_handle_bitmap_export_writes_3mfs(tmp_path: Path) -> None:
    """测试位图导出处理器是否正确生成3MF文件

    验证handle_bitmap_export函数能否正确生成标准3MF和Bambu 3MF文件

    Args:
        tmp_path: pytest提供的临时路径
    """
    lut_path = tmp_path / "lut.npy"
    img_path = tmp_path / "img.png"
    _make_demo_lut(lut_path)
    _make_demo_image(img_path, lut_path)

    out_dir = tmp_path / "out"
    job = Job(job_id="job_test", out_dir=str(out_dir))

    result = handle_bitmap_export(
        job,
        {
            "image_path": str(img_path),
            "lut_path": str(lut_path),
            "n_layers": 5,
            "target_width_mm": 6,
            "nozzle_width_mm": 0.6,
            "output_format": "3mf",
            "export_3mf_standard": True,
            "export_3mf_bambu": True,
            "bambu_template": str(Path(__file__).resolve().parents[5] / "data" / "rgbw_cubes.3mf"),
        },
        lambda *_args: None,
    )

    # 验证元数据文件存在且格式正确
    assert Path(result["meta"]).exists()
    meta = json.loads(Path(result["meta"]).read_text(encoding="utf-8"))
    assert meta["artifacts"]["standard_3mf"].endswith(".3mf")
    assert meta["artifacts"]["bambu_3mf"].endswith(".3mf")

    # 验证输出文件都存在
    assert Path(result["standard_3mf"]).exists()
    assert Path(result["bambu_3mf"]).exists()
    assert Path(result["preview2d"]).exists()


def test_engine_ndjson_integration(tmp_path: Path) -> None:
    """测试引擎的NDJSON集成

    通过子进程启动引擎主程序，提交位图导出请求，
    验证能否正确接收job.done事件并生成3MF文件

    Args:
        tmp_path: pytest提供的临时路径
    """
    # 最小化端到端测试：启动engine.main，提交bitmap.export，等待job.done
    lut_path = tmp_path / "lut.npy"
    img_path = tmp_path / "img.png"
    _make_demo_lut(lut_path)
    _make_demo_image(img_path, lut_path)

    out_dir = tmp_path / "out_engine"
    req = {
        "jsonrpc": "2.0",
        "id": "req_1",
        "method": "bitmap.export",
        "params": {
            "image_path": str(img_path),
            "lut_path": str(lut_path),
            "n_layers": 5,
            "target_width_mm": 6,
            "nozzle_width_mm": 0.6,
            "output_format": "3mf",
            "export_3mf_standard": True,
            "export_3mf_bambu": True,
            "out_dir": str(out_dir),
            "bambu_template": str(Path(__file__).resolve().parents[5] / "data" / "rgbw_cubes.3mf"),
        },
    }

    # 启动引擎子进程
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "oc_engine.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path(__file__).resolve().parents[2]),
        text=True,
    )
    assert proc.stdin and proc.stdout
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()

    # 等待job.done事件，超时25秒
    got_done = False
    deadline = time.time() + 25
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        payload = json.loads(line)
        if payload.get("event") == "job.done":
            got_done = True
            result = payload.get("result", {})
            assert Path(result["standard_3mf"]).exists()
            assert Path(result["bambu_3mf"]).exists()
            break

    proc.kill()
    assert got_done, "未收到job.done事件"
