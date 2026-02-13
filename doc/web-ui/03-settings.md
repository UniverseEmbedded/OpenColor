# 设置设计

设置分为APP设置和项目设置两类，分别存储在不同位置，作用范围不同。

## APP设置

### 存储位置

```
Windows: %LOCALAPPDATA%\OpenColor\settings.json
```

### 设置项

| 设置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| 语言 | string | auto | 中文/英文/自动 |
| 主题 | string | auto | 深色/浅色/跟随系统 |
| 当前工作区 | string | - | 上次打开的工作区路径 |
| 最近工作区 | array | [] | 最近使用的工作区路径列表 |
| 窗口尺寸 | object | - | 上次关闭时的窗口宽高 |
| 引擎路径 | string | auto | Python引擎位置，auto表示自动检测 |
| GPU加速 | boolean | true | 默认启用Vulkan加速 |
| 日志级别 | string | info | 调试/debug/信息/info/警告/warn/错误/error |

### 设置文件示例

```json
{
  "locale": "zh-CN",
  "theme": "dark",
  "current_workspace": "C:\\Users\\xxx\\Documents\\OpenColor\\default",
  "recent_workspaces": [
    "C:\\Users\\xxx\\Documents\\OpenColor\\20250211_143052",
    "D:\\Projects\\项目C"
  ],
  "window_size": {
    "width": 1280,
    "height": 800
  },
  "engine_path": "auto",
  "gpu_acceleration": true,
  "log_level": "info"
}
```

## 项目设置

### 存储位置

工作区根目录的 `settings.json`：

```
{workspace}/settings.json
```

### 设置项

| 设置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| 默认耗材组 | string | - | 该工作区默认使用的耗材组ID |
| 默认层高 | number | 0.2 | 该工作区默认层高，单位mm |
| 默认模型 | string | - | 由耗材组和层高自动确定的模型 |
| 导出偏好 | object | - | 默认导出选项 |
| 叠色像素参数 | object | - | 默认处理参数 |

### 模型与层高的关系

同一耗材组在不同层高下有独立的校准数据和模型：

```
MyPLA耗材组
├── 0.2mm层高 → model_MyPLA_0.2mm.json
├── 0.3mm层高 → model_MyPLA_0.3mm.json
└── 用户根据打印需求选择
```

层高作为模型维度，影响：
- 校准板生成（层高参数写入规格）
- 模型训练（层高作为训练参数）
- 叠色像素生成（使用对应层高的模型）

### 设置文件示例

```json
{
  "default_material_group": "oc1_mg_MyPLA_4c",
  "default_layer_height": 0.2,
  "default_model": "oc1_mg_MyPLA_0.2mm_xxx",
  "export_preferences": {
    "export_stl": true,
    "export_3mf": true,
    "use_cpp_acceleration": true,
    "mesh_repair": true
  },
  "mask_generation_params": {
    "superres_enabled": true,
    "superres_scale": 2,
    "layer0_bias_enabled": true,
    "postprocess_mode": "joint"
  }
}
```

## 界面组织

### 设置标签页二级导航

| 子项 | 类型 | 内容 |
|------|------|------|
| 通用 | APP设置 | 语言、主题、窗口 |
| 工作区 | APP设置 | 工作区管理、切换 |
| 引擎 | APP设置 | 引擎路径、GPU、日志 |
| 项目 | 项目设置 | 当前工作区的默认配置 |

### 项目设置页面内容

- 默认耗材组选择
- 默认层高选择（根据耗材组显示可用层高）
- 当前使用的模型显示（耗材组+层高自动确定）
- 导出偏好设置
- 叠色像素默认参数

## 设置优先级

当存在冲突时，优先级从高到低：

1. 环节页面中的实时配置
2. 项目设置中的默认值
3. 应用硬编码的默认值

示例：叠色像素生成
- 用户在环节页面修改了超分辨率倍数 → 使用页面值
- 用户未修改 → 使用项目设置中的默认值
- 项目设置未配置 → 使用硬编码默认值（2倍）
