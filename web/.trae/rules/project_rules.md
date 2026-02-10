# OpenColor Web-UI 项目规则

## 常见预设/偏见错误

### 1. 数据字段假设
**错误**: 假设材料组使用 `materials` 字段存储材料列表
**实际**: 使用 `slots` 字段，每个 slot 包含 `filamentId` 和 `filament` 对象
```javascript
// 错误
profile.materials?.length

// 正确
profile.slots?.length
```

### 2. 文件保存方式
**错误**: 直接保存文件到目标目录，不更新资源库索引
**实际**: 必须先保存文件，然后调用 `upsert_library_item` 更新索引
```javascript
// 错误
await invoke("save_text_file", { path, content });

// 正确
await invoke("save_text_file", { path, content });
await invoke("upsert_library_item", { path: relativePath, kind, short, long });
```

### 3. 文件名生成
**错误**: 在文件名中包含用户自定义名称
**实际**: 文件名只应包含类型标识和短哈希，时间戳放在子文件夹
```javascript
// 错误
`oc1_mg_${channels}c_${name}_${hash}.json`

// 正确
`oc1_mg_${channels}c_${hash}.json`
// 保存路径: Profiles/YYYYMMDD_HHMMSS/oc1_mg_4c_a3b5c8d2.json
```

### 4. 事件传递
**错误**: 假设子组件事件会自动传递到父组件
**实际**: 需要在每一层组件中显式绑定和触发事件
```vue
<!-- AppMain.vue -->
<MaterialsView 
  @addFilament="$emit('addFilament', $event)"
/>

<!-- App.vue -->
<AppMain 
  @addFilament="handleAddFilament"
/>
```

### 5. 样式覆盖
**错误**: 假设组件样式是独立的
**实际**: 全局 CSS 可能覆盖组件样式（如 `.mat-subnav{display:none}`）
```css
/* 检查全局样式是否隐藏了组件 */
.mat-subnav { display: none } /* 这会导致切换按钮不可见 */
```

### 6. 数据加载来源
**错误**: 假设数据从后端 API 加载
**实际**: 优先从资源库索引 `list_library_files` 加载
```javascript
// 错误
const result = await invoke("engine_request", { method: "filament.list" });

// 正确
const items = await invoke("list_library_files");
const filamentItems = items.filter(item => item.kind === 'filament');
```

### 7. 相对路径处理
**错误**: 使用绝对路径存储文件位置
**实际**: 始终使用相对于 OpenColor 根目录的路径
```javascript
// 错误
const path = "C:/Users/xxx/Documents/OpenColor/Profiles/file.json";

// 正确
const relativePath = "Profiles/20260206_150404/oc1_mg_4c_a3b5c8d2.json";
```

### 8. i18n 信息存储
**错误**: 在文件名中编码 i18n 信息
**实际**: i18n 信息存储在资源库索引的 `short` 字段中
```javascript
// 错误
文件名: "RGBW_4色材料组.json"

// 正确
文件名: "oc1_mg_4c_a3b5c8d2.json"
short: { kind: "material_group", name: "RGBW 配置", channelCount: 4 }
```

## 开发检查清单

- [ ] 检查数据字段名（slots vs materials）
- [ ] 确认文件保存后更新资源库索引
- [ ] 文件名不包含用户自定义名称
- [ ] 事件绑定在每一层组件中显式声明
- [ ] 检查全局 CSS 是否影响组件显示
- [ ] 使用相对路径存储文件位置
- [ ] i18n 信息通过 short 字段提供
