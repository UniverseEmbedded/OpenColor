import { ref, computed } from "vue";

/**
 * 材料配置管理组合式函数
 * 
 * 概念说明：
 * - 耗材(Filament): 具体的打印耗材，如"Bambu Lab PLA Basic 白色"
 * - 材料组(MaterialGroup/Profile): 一组耗材的集合，用于打印任务，如"我的RGBW配置"
 * 
 * @param {Function} invoke - Tauri 调用函数
 * @returns {Object} 材料配置管理相关状态和方法
 */
export const useMaterials = (invoke) => {
  // ========== 状态 ==========
  
  // 耗材列表（具体的打印耗材）
  const filaments = ref([]);
  
  // 材料组列表（耗材的集合配置）
  const materialGroups = ref([]);
  
  // 当前选中的材料组
  const currentGroup = ref(null);
  
  // 加载状态
  const isLoading = ref(false);
  
  // 错误信息
  const error = ref(null);

  // ========== 默认数据 ==========
  
  /**
   * 模板用耗材定义（仅用于创建模板时的初始数据，不直接显示在耗材列表中）
   * 包含理想颜色(targetColor)和实际颜色(actualColor)
   */
  const templateFilaments = {
    white: { 
      id: "fil_white_01", name: "White", brand: "Generic", color: "白色", type: "PLA",
      targetColor: { hex: "#f5f5f5", rgba: [245, 245, 245, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    black: { 
      id: "fil_black_01", name: "Black", brand: "Generic", color: "黑色", type: "PLA",
      targetColor: { hex: "#191919", rgba: [25, 25, 25, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    red: { 
      id: "fil_red_01", name: "Red", brand: "Generic", color: "红色", type: "PLA",
      targetColor: { hex: "#e64646", rgba: [230, 70, 70, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    green: { 
      id: "fil_green_01", name: "Green", brand: "Generic", color: "绿色", type: "PLA",
      targetColor: { hex: "#46d278", rgba: [70, 210, 120, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    blue: { 
      id: "fil_blue_01", name: "Blue", brand: "Generic", color: "蓝色", type: "PLA",
      targetColor: { hex: "#508cf0", rgba: [80, 140, 240, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    cyan: { 
      id: "fil_cyan_01", name: "Cyan", brand: "Generic", color: "青色", type: "PLA",
      targetColor: { hex: "#46d2d2", rgba: [70, 210, 210, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    magenta: { 
      id: "fil_magenta_01", name: "Magenta", brand: "Generic", color: "品红", type: "PLA",
      targetColor: { hex: "#dc5ad2", rgba: [220, 90, 210, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    yellow: { 
      id: "fil_yellow_01", name: "Yellow", brand: "Generic", color: "黄色", type: "PLA",
      targetColor: { hex: "#f0d25a", rgba: [240, 210, 90, 255] },
      actualColor: { hex: "", rgba: [] }
    },
    transparent: { 
      id: "fil_trans_01", name: "Transparent", brand: "Generic", color: "透明", type: "PLA", isTransparent: true,
      targetColor: { hex: "#e8f4f8", rgba: [232, 244, 248, 180] },
      actualColor: { hex: "", rgba: [] }
    },
  };

  /**
   * 预设材料组模板
   */
  const groupTemplates = [
    {
      id: "template_rgb",
      name: "RGB",
      descriptionKey: "template.rgb.desc",
      channelCount: 3,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
      ]
    },
    {
      id: "template_rgbw",
      name: "RGB-W",
      descriptionKey: "template.rgbw.desc",
      channelCount: 4,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
        { slotIndex: 3, filamentId: "fil_white_01", filament: templateFilaments.white },
      ]
    },
    {
      id: "template_rgbwk",
      name: "RGB-WK",
      descriptionKey: "template.rgbwk.desc",
      channelCount: 5,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
        { slotIndex: 3, filamentId: "fil_white_01", filament: templateFilaments.white },
        { slotIndex: 4, filamentId: "fil_black_01", filament: templateFilaments.black },
      ]
    },
    {
      id: "template_rgbywk",
      name: "RGB-Y-WK",
      descriptionKey: "template.rgbywk.desc",
      channelCount: 6,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
        { slotIndex: 3, filamentId: "fil_yellow_01", filament: templateFilaments.yellow },
        { slotIndex: 4, filamentId: "fil_white_01", filament: templateFilaments.white },
        { slotIndex: 5, filamentId: "fil_black_01", filament: templateFilaments.black },
      ]
    },
    {
      id: "template_rgbcymwk",
      name: "RGB-CYM-WK",
      descriptionKey: "template.rgbcymwk.desc",
      channelCount: 8,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
        { slotIndex: 3, filamentId: "fil_cyan_01", filament: templateFilaments.cyan },
        { slotIndex: 4, filamentId: "fil_magenta_01", filament: templateFilaments.magenta },
        { slotIndex: 5, filamentId: "fil_yellow_01", filament: templateFilaments.yellow },
        { slotIndex: 6, filamentId: "fil_white_01", filament: templateFilaments.white },
        { slotIndex: 7, filamentId: "fil_black_01", filament: templateFilaments.black },
      ]
    },
    {
      id: "template_rgbcymwkt",
      name: "RGB-CYM-WKT",
      descriptionKey: "template.rgbcymwkt.desc",
      channelCount: 9,
      slots: [
        { slotIndex: 0, filamentId: "fil_red_01", filament: templateFilaments.red },
        { slotIndex: 1, filamentId: "fil_green_01", filament: templateFilaments.green },
        { slotIndex: 2, filamentId: "fil_blue_01", filament: templateFilaments.blue },
        { slotIndex: 3, filamentId: "fil_cyan_01", filament: templateFilaments.cyan },
        { slotIndex: 4, filamentId: "fil_magenta_01", filament: templateFilaments.magenta },
        { slotIndex: 5, filamentId: "fil_yellow_01", filament: templateFilaments.yellow },
        { slotIndex: 6, filamentId: "fil_white_01", filament: templateFilaments.white },
        { slotIndex: 7, filamentId: "fil_black_01", filament: templateFilaments.black },
        { slotIndex: 8, filamentId: "fil_trans_01", filament: templateFilaments.transparent },
      ]
    },
  ];

  // ========== 工具函数 ==========
  
  const generateId = () => `group_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  const generateDefaultName = (count) => `材料组 ${count + 1}`;

  // ========== 耗材管理 ==========
  
  /**
   * 加载耗材列表
   * 从资源库索引加载，不再使用默认伪数据
   */
  const loadFilaments = async () => {
    try {
      // 从资源库索引加载
      const items = await invoke("list_library_files");
      const filamentItems = items.filter(item => item.kind === 'filament');
      
      const loadedFilaments = [];
      for (const item of filamentItems) {
        try {
          const content = await invoke("read_text_file", { path: item.path });
          const filament = JSON.parse(content);
          loadedFilaments.push({
            ...filament,
            id: item.id || filament.id,
            path: item.path,
          });
        } catch (e) {
          console.error(`加载耗材失败: ${item.path}`, e);
        }
      }
      filaments.value = loadedFilaments;
      console.log(`[耗材] 从资源库加载了 ${loadedFilaments.length} 个耗材`);
    } catch (e) {
      console.error("加载耗材列表失败:", e);
      filaments.value = [];
    }
  };

  /**
   * 生成时间戳子文件夹名 (YYYYMMDD_HHMMSS)
   */
  const generateTimestampFolder = () => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    const h = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    return `${y}${m}${d}_${h}${min}${s}`;
  };

  /**
   * 生成耗材文件名 (不含时间戳)
   * 格式: oc1_fl_<type>_<hash>.json
   */
  const generateFilamentFileName = (filament) => {
    const type = (filament.type || 'PLA').toLowerCase();
    const hash = Math.random().toString(36).substr(2, 8);
    return `oc1_fl_${type}_${hash}.json`;
  };

  /**
   * 添加新耗材
   */
  const addFilament = async (filament) => {
    try {
      const newFilament = {
        id: `fil_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        ...filament,
        createdAt: Date.now(),
      };
      
      // 获取 Filaments 目录路径
      const libPaths = await invoke("get_library_paths");
      
      // 创建时间戳子文件夹
      const timestampFolder = generateTimestampFolder();
      const folderPath = `${libPaths.filaments}/${timestampFolder}`;
      
      // 生成文件名 (不含时间戳)
      const fileName = generateFilamentFileName(newFilament);
      const content = JSON.stringify(newFilament, null, 2);
      const filePath = `${folderPath}/${fileName}`;
      
      // 确保目录存在并保存文件
      await invoke("create_dir", { path: folderPath });
      await invoke("save_text_file", {
        path: filePath,
        content: content,
      });
      
      // 更新资源库索引（带i18n信息）
      const relativePath = `Filaments/${timestampFolder}/${fileName}`;
      const shortInfo = {
        kind: "filament",
        name: newFilament.name,
        brand: newFilament.brand,
        type: newFilament.type,
        color: newFilament.color,
        isTransparent: newFilament.isTransparent || false
      };
      
      await invoke("upsert_library_item", {
        path: relativePath,
        kind: "filament",
        short: shortInfo,
        long: {
          method: "filament.save",
          filament: newFilament
        }
      });
      
      console.log("[耗材] 已保存:", relativePath);
      
      filaments.value.push(newFilament);
      return newFilament;
    } catch (e) {
      console.error("添加耗材失败:", e);
      throw e;
    }
  };

  // 临时耗材存储（用于模板创建流程）
  const tempFilaments = ref([]);

  /**
   * 从模板槽位创建临时耗材条目
   * 只创建内存中的临时耗材，不保存到文件
   * 返回临时耗材映射关系，供后续使用
   */
  const createTempFilamentsFromTemplate = (slots) => {
    const createdTempFilaments = [];
    const slotFilamentMap = new Map(); // slotIndex -> filamentId
    
    for (const slot of slots) {
      if (!slot.filament) continue;
      
      const templateFil = slot.filament;
      
      // 检查是否已存在相同理想颜色的耗材（包括临时耗材）
      const existingFilament = filaments.value.find(f => 
        f.targetColor?.hex === templateFil.targetColor?.hex
      ) || tempFilaments.value.find(f => 
        f.targetColor?.hex === templateFil.targetColor?.hex
      );
      
      if (existingFilament) {
        // 复用已有耗材
        slotFilamentMap.set(slot.slotIndex, existingFilament.id);
      } else {
        // 创建临时耗材（不保存到文件）
        const tempFilament = {
          id: `fil_temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          name: templateFil.name,
          brand: templateFil.brand,
          color: templateFil.color,
          type: templateFil.type || "PLA",
          isTransparent: templateFil.isTransparent || false,
          targetColor: templateFil.targetColor,
          actualColor: { hex: "", rgba: [] }, // 实际颜色初始为空
          isTemp: true, // 标记为临时耗材
          createdAt: Date.now(),
        };
        tempFilaments.value.push(tempFilament);
        createdTempFilaments.push(tempFilament);
        slotFilamentMap.set(slot.slotIndex, tempFilament.id);
      }
    }
    
    return { createdTempFilaments, slotFilamentMap };
  };

  /**
   * 保存临时耗材到数据库
   * 在材料组创建成功后调用
   */
  const saveTempFilaments = async () => {
    const savedFilaments = [];
    
    for (const tempFil of tempFilaments.value) {
      try {
        // 移除临时标记并保存
        const { isTemp, ...filamentData } = tempFil;
        const savedFilament = await addFilament(filamentData);
        savedFilaments.push(savedFilament);
      } catch (e) {
        console.error("保存临时耗材失败:", tempFil.name, e);
      }
    }
    
    // 清空临时耗材列表
    tempFilaments.value = [];
    
    return savedFilaments;
  };

  /**
   * 清理临时耗材
   * 在取消创建或创建失败时调用
   */
  const clearTempFilaments = () => {
    tempFilaments.value = [];
  };

  // ========== 材料组管理 ==========
  
  /**
   * 创建新材料组
   * @param {string} name 材料组名称
   * @param {number} channelCount 通道数量（4或8）
   * @param {Array} slots 槽位配置 [{filamentId, slotIndex}, ...]
   */
  const createGroup = (name, channelCount = 4, slots = []) => {
    // 如果没有提供slots，使用模板耗材填充
    const templateList = channelCount === 4 
      ? [templateFilaments.red, templateFilaments.green, templateFilaments.blue, templateFilaments.white]
      : [templateFilaments.red, templateFilaments.green, templateFilaments.blue, templateFilaments.cyan, 
         templateFilaments.magenta, templateFilaments.yellow, templateFilaments.white, templateFilaments.black];
    const finalSlots = slots.length > 0 
      ? slots 
      : templateList.slice(0, channelCount).map((f, i) => ({
          slotIndex: i,
          filamentId: f.id,
          filament: f
        }));

    return {
      id: generateId(),
      name: name || generateDefaultName(materialGroups.value.length),
      version: 1,
      channelCount: channelCount,
      slots: finalSlots,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
  };

  /**
   * 加载材料组列表
   */
  const loadGroups = async () => {
    isLoading.value = true;
    error.value = null;
    try {
      // 尝试从资源库加载（旧方式兼容）
      const items = await invoke("list_library_files");
      const groupItems = items.filter(item => item.kind === 'profile' || item.kind === 'material_group');

      const loadedGroups = [];
      for (const item of groupItems) {
        try {
          const content = await invoke("read_text_file", { path: item.path });
          const group = JSON.parse(content);
          loadedGroups.push({
            ...group,
            id: item.id || group.id,
            path: item.path,
          });
        } catch (e) {
          console.error(`加载材料组失败: ${item.path}`, e);
        }
      }

      materialGroups.value = loadedGroups;

      // 如果没有选中任何组，默认选中第一个
      if (!currentGroup.value && loadedGroups.length > 0) {
        currentGroup.value = loadedGroups[0];
      }
    } catch (e) {
      console.error("加载材料组列表失败:", e);
      error.value = e.message || "加载失败";
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * 生成材料组文件名 (不含时间戳)
   * 格式: oc1_mg_<channel>c_<hash>.json
   */
  const generateGroupFileName = (group) => {
    const channels = group.channelCount || 4;
    const hash = Math.random().toString(36).substr(2, 8);
    return `oc1_mg_${channels}c_${hash}.json`;
  };

  /**
   * 保存材料组
   * @param {Object} group 材料组对象
   */
  const saveGroup = async (group) => {
    if (!group) return;
    error.value = null;
    try {
      const groupToSave = {
        ...group,
        updatedAt: Date.now(),
      };

      // 获取 Profiles 目录路径
      const libPaths = await invoke("get_library_paths");
      
      // 创建时间戳子文件夹
      const timestampFolder = generateTimestampFolder();
      const folderPath = `${libPaths.profiles}/${timestampFolder}`;
      
      // 生成文件名 (不含时间戳)
      const fileName = generateGroupFileName(groupToSave);
      const content = JSON.stringify(groupToSave, null, 2);
      const filePath = `${folderPath}/${fileName}`;
      
      // 确保目录存在并保存文件
      await invoke("create_dir", { path: folderPath });
      await invoke("save_text_file", {
        path: filePath,
        content: content,
      });
      
      // 更新资源库索引（带i18n信息）
      const relativePath = `Profiles/${timestampFolder}/${fileName}`;
      const shortInfo = {
        kind: "material_group",
        name: groupToSave.name,
        channelCount: groupToSave.channelCount,
        slotCount: groupToSave.slots?.length || 0,
        assignedCount: groupToSave.slots?.filter(s => s.filamentId)?.length || 0
      };
      
      await invoke("upsert_library_item", {
        path: relativePath,
        kind: "profile",
        short: shortInfo,
        long: {
          method: "material_group.save",
          group: groupToSave
        }
      });
      
      console.log("[材料组] 已保存到资源库索引:", relativePath);

      // 更新本地列表
      const index = materialGroups.value.findIndex(g => g.id === groupToSave.id);
      if (index !== -1) {
        materialGroups.value[index] = groupToSave;
      } else {
        materialGroups.value.push(groupToSave);
      }
      
      return groupToSave;
    } catch (e) {
      console.error("保存材料组失败:", e);
      error.value = e.message || "保存失败";
      throw e;
    }
  };

  /**
   * 创建并保存新材料组
   */
  const createAndSaveGroup = async (name, channelCount = 4, slots = []) => {
    const newGroup = createGroup(name, channelCount, slots);
    await saveGroup(newGroup);
    currentGroup.value = newGroup;
    return newGroup;
  };

  /**
   * 选择材料组
   */
  const selectGroup = (groupId) => {
    const group = materialGroups.value.find(g => g.id === groupId);
    if (group) {
      currentGroup.value = group;
    }
  };

  /**
   * 导出材料组为 JSON 文件
   */
  const exportGroup = async (group, saveDialog) => {
    if (!group) return;
    try {
      const picked = await saveDialog({
        filters: [{ name: "JSON", extensions: ["json"] }],
        defaultPath: `${group.name}.json`,
      });
      if (picked) {
        const content = JSON.stringify(group, null, 2);
        await invoke("save_text_file", {
          path: picked,
          content: content,
        });
      }
    } catch (e) {
      console.error("导出材料组失败:", e);
      throw e;
    }
  };

  /**
   * 从 JSON 文件导入材料组
   */
  const importGroup = async (openDialog) => {
    try {
      const picked = await openDialog({
        multiple: false,
        filters: [{ name: "JSON", extensions: ["json"] }],
      });
      if (typeof picked === "string" && picked) {
        const content = await invoke("read_text_file", { path: picked });
        const group = JSON.parse(content);
        
        // 验证格式
        if (!group.slots || !Array.isArray(group.slots)) {
          // 尝试兼容旧格式（materials）
          if (group.materials && Array.isArray(group.materials)) {
            group.slots = group.materials.map((m, i) => ({
              slotIndex: i,
              filamentId: m.id || `fil_${i}`,
              filament: m
            }));
          } else {
            throw new Error("无效的材料组文件格式");
          }
        }
        
        // 赋予新ID避免冲突
        group.id = generateId();
        group.name = `${group.name || "导入配置"} (导入)`;
        group.createdAt = Date.now();
        group.updatedAt = Date.now();

        await saveGroup(group);
        return group;
      }
    } catch (e) {
      console.error("导入材料组失败:", e);
      throw e;
    }
  };

  /**
   * 获取用于引擎的材料列表格式
   */
  const getMaterialsForEngine = (group) => {
    if (!group || !group.slots) return [];
    
    return group.slots.map(slot => {
      const filament = slot.filament || filaments.value.find(f => f.id === slot.filamentId);
      return {
        name: filament?.name || `Slot ${slot.slotIndex + 1}`,
        rgba: filament?.rgba || [200, 200, 200, 255],
      };
    });
  };

  /**
   * 更新材料组
   */
  const updateGroup = (groupId, updates) => {
    const index = materialGroups.value.findIndex(g => g.id === groupId);
    if (index !== -1) {
      materialGroups.value[index] = {
        ...materialGroups.value[index],
        ...updates,
        updatedAt: Date.now(),
      };
      if (currentGroup.value?.id === groupId) {
        currentGroup.value = materialGroups.value[index];
      }
    }
  };

  // ========== 返回 ==========
  
  return {
    // 状态
    filaments,
    materialGroups,
    currentGroup,
    isLoading,
    error,
    
    // 计算属性
    hasGroups: computed(() => materialGroups.value.length > 0),
    groupCount: computed(() => materialGroups.value.length),
    filamentCount: computed(() => filaments.value.length),
    
    // 状态
    tempFilaments,
    
    // 耗材方法
    loadFilaments,
    addFilament,
    createTempFilamentsFromTemplate,
    saveTempFilaments,
    clearTempFilaments,
    
    // 材料组方法
    loadGroups,
    createGroup,
    saveGroup,
    createAndSaveGroup,
    selectGroup,
    exportGroup,
    importGroup,
    getMaterialsForEngine,
    updateGroup,
    
    // 常量
    templateFilaments,
    groupTemplates,
    
    // 兼容旧 API（profile -> group）
    profiles: materialGroups,
    currentProfile: currentGroup,
    loadProfiles: loadGroups,
    createProfile: createGroup,
    saveProfile: saveGroup,
    createAndSaveProfile: createAndSaveGroup,
    selectProfile: selectGroup,
    exportProfile: exportGroup,
    importProfile: importGroup,
    getMaterialsForProfile: getMaterialsForEngine,
    updateProfile: updateGroup,
  };
};
