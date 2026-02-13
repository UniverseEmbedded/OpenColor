# 工作区设计

## 概述

工作区是OpenColor的数据存储单元，每个工作区包含完整的7个环节输出目录。支持多工作区切换，默认使用固定路径的工作区。

## 目录结构

### 默认工作区路径

```
C:\Users\{用户名}\Documents\OpenColor\
├── default\                    # 默认工作区
│   ├── index.json              # 工作区元数据
│   ├── calib_board\            # 环节1：校准板生成
│   ├── calib_photo\            # 环节2：照片校正
│   ├── calib_sample\           # 环节3：样本提取
│   ├── calib_model\            # 环节4：模型训练
│   ├── gen_masks\              # 环节5：叠色像素生成
│   ├── gen_vector\             # 环节6：矢量化
│   └── gen_3mf\                # 环节7：模型导出
```

### 多工作区结构

```
C:\Users\{用户名}\Documents\OpenColor\
├── default\                    # 默认工作区
│   ├── index.json
│   └── ...
├── 20250211_143052\            # 用户新建工作区（时间戳命名）
│   ├── index.json              # 显示名称："我的项目A"
│   └── ...
├── 20250212_090123\            # 用户新建工作区
│   ├── index.json              # 显示名称："客户订单B"
│   └── ...
└── D:\Projects\项目C\          # 用户自定义路径工作区
    ├── index.json
    └── ...
```

## index.json 格式

每个工作区根目录包含 index.json，存储工作区元数据：

```json
{
  "name": "我的项目A",
  "created": "2025-02-11T14:30:52",
  "version": "1.0"
}
```

字段说明：
- name：工作区显示名称，用户可自定义
- created：创建时间，ISO 8601格式
- version：工作区格式版本，用于未来兼容性

## 应用设置

应用设置存储在系统应用数据目录，与工作区分离：

```
Windows: %LOCALAPPDATA%\OpenColor\settings.json
```

settings.json 包含工作区相关配置：

```json
{
  "locale": "zh-CN",
  "theme": "dark",
  "current_workspace": "C:\\Users\\xxx\\Documents\\OpenColor\\default",
  "recent_workspaces": [
    "C:\\Users\\xxx\\Documents\\OpenColor\\20250211_143052",
    "D:\\Projects\\项目C"
  ]
}
```

## 工作区管理

### 首次启动

1. 检测是否存在默认工作区（Documents\OpenColor\default）
2. 不存在则自动创建目录结构和 index.json
3. 自动设置为当前工作区

### 新建工作区

提供两种选项：

**选项A：使用默认位置**
- 在 Documents\OpenColor\ 下创建时间戳命名的目录
- 目录格式：YYYYMMDD_HHMMSS
- 用户只需输入显示名称

**选项B：指定自定义位置**
- 用户选择任意目录
- 在该目录下创建工作区结构和 index.json

### 切换工作区

- 从设置中选择最近工作区
- 或打开其他位置的工作区
- 切换时重新加载该工作区的文件索引

### 删除工作区

- 仅从最近列表移除，不删除实际文件
- 用户需手动删除目录

## 与旧版差异

| 方面 | 旧版 | 新版 |
|------|------|------|
| 工作区数量 | 单一固定 | 多工作区支持 |
| 根目录 | Documents\OpenColor | 可配置，默认同上 |
| 子目录结构 | Captures/Profiles/Exports等 | 按7个环节命名 |
| 索引文件 | .index/library.json | index.json（每个工作区独立）|
| 元数据 | 文件级元数据 | 工作区级元数据 |

## 界面集成

### 大窗模式

侧边栏底部显示当前工作区名称，点击展开：
- 当前工作区名称和路径
- 最近工作区列表（最多5个）
- 新建工作区按钮
- 打开其他工作区按钮

### 小窗模式

抽屉菜单底部显示当前工作区，点击展开工作区管理选项。

### 设置页面

工作区管理子页面：
- 当前工作区信息
- 最近工作区列表（可删除记录）
- 新建工作区按钮
- 打开其他工作区按钮
- 设置默认工作区按钮
