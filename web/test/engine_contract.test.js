import { describe, it, expect } from "vitest";

import { buildBitmapExportParams, normalizeBitmapResult } from "../src/engine_contract.js";

/**
 * 引擎契约测试套件
 * 测试位图导出参数构建和结果归一化功能
 */
describe("engine_contract", () => {
  /**
   * 测试：默认导出格式为 STL
   */
  it("buildBitmapExportParams: stl by default", () => {
    const p = buildBitmapExportParams({
      imagePath: "/tmp/a.png",
      lutPath: "/tmp/lut.npy",
      nozzleWidthMm: 0.42,
      targetWidthMm: 60,
      nLayers: 5,
      outputFormat: "stl",
      outDir: "",
    });
    expect(p.output_format).toBe("stl");
    expect(p.export_3mf_standard).toBe(false);
    expect(p.export_3mf_bambu).toBe(false);
  });

  /**
   * 测试：3MF 格式导出时同时启用标准和 Bambu 导出器
   */
  it("buildBitmapExportParams: 3mf implies both exporters", () => {
    const p = buildBitmapExportParams({
      imagePath: "/tmp/a.png",
      lutPath: "/tmp/lut.npy",
      nozzleWidthMm: 0.42,
      targetWidthMm: 60,
      nLayers: 5,
      outputFormat: "3mf",
      outDir: "/tmp/out",
    });
    expect(p.output_format).toBe("3mf");
    expect(p.export_3mf_standard).toBe(true);
    expect(p.export_3mf_bambu).toBe(true);
    expect(p.out_dir).toBe("/tmp/out");
  });

  /**
   * 测试：结果归一化的防御性默认值
   */
  it("normalizeBitmapResult: defensive defaults", () => {
    const r = normalizeBitmapResult({ out_dir: "/tmp/out", stls: ["a", "b"], standard_3mf: "s.3mf" });
    expect(r.outDir).toBe("/tmp/out");
    expect(r.stls.length).toBe(2);
    expect(r.standard3mf).toBe("s.3mf");
    expect(r.bambu3mf).toBe("");
  });
});
