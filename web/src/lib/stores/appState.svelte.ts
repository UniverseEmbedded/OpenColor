/**
 * 应用全局状态管理
 * 使用 Svelte 5 Runes 实现
 */

// 当前视图
let currentView = $state("generate");

// 基础对话框状态
let helpOpen = $state(false);
let aboutOpen = $state(false);

// 输入设置
let inputKind = $state("svg");
let inputPath = $state("");

// 输出设置
let outputFormat = $state("stl");
let outputDir = $state("");
let wmm = $state(120);
let hmm = $state(120);
let layers = $state(6);

export function getAppState() {
  return {
    get currentView() { return currentView; },
    set currentView(v) { currentView = v; },
    
    get helpOpen() { return helpOpen; },
    set helpOpen(v) { helpOpen = v; },
    
    get aboutOpen() { return aboutOpen; },
    set aboutOpen(v) { aboutOpen = v; },
    
    get inputKind() { return inputKind; },
    set inputKind(v) { inputKind = v; },
    
    get inputPath() { return inputPath; },
    set inputPath(v) { inputPath = v; },
    
    get outputFormat() { return outputFormat; },
    set outputFormat(v) { outputFormat = v; },
    
    get outputDir() { return outputDir; },
    set outputDir(v) { outputDir = v; },
    
    get wmm() { return wmm; },
    set wmm(v) { wmm = v; },
    
    get hmm() { return hmm; },
    set hmm(v) { hmm = v; },
    
    get layers() { return layers; },
    set layers(v) { layers = v; },
  };
}
