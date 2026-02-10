#include "vulkan_context.h"
#include "vulkan_utils.h"
#include "vulkan_shader.h"
#include <vector>

namespace opencolor {
namespace solver {

// 全局静态变量 - 用于线程安全的上下文管理
static std::mutex g_solver_vk_mutex;                    // 互斥锁，保护 Vulkan 上下文初始化/销毁的线程安全
static SolverVulkanContext g_solver_vk_ctx;             // 求解器 Vulkan 上下文全局实例
static bool g_solver_vk_ready = false;                  // 标记 Vulkan 上下文是否已初始化完成
static std::atomic<int> g_solver_vk_users{0};           // 引用计数，跟踪当前使用 Vulkan 上下文的用户数量

// 获取求解器 Vulkan 上下文引用
SolverVulkanContext& get_solver_vulkan_context() {
    return g_solver_vk_ctx;
}

// 获取求解器 Vulkan 互斥锁引用，用于外部同步
std::mutex& get_solver_vulkan_mutex() {
    return g_solver_vk_mutex;
}

// 检查 Vulkan 上下文是否已准备就绪
bool is_solver_vulkan_ready() {
    return g_solver_vk_ready;
}

// 获取当前使用 Vulkan 上下文的用户数量
std::atomic<int>& get_solver_vulkan_users() {
    return g_solver_vk_users;
}

// 初始化求解器 Vulkan 上下文
// 创建 Vulkan 实例、选择物理设备、创建逻辑设备和计算管线
void init_solver_vulkan_context() {
    std::lock_guard<std::mutex> lock(g_solver_vk_mutex);
    // 如果已经初始化，直接返回，避免重复初始化
    if (g_solver_vk_ready) {
        return;
    }

    // 配置 Vulkan 应用程序信息
    VkApplicationInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;      // 结构体类型
    ai.pApplicationName = "opencolor_solver";           // 应用程序名称
    ai.applicationVersion = VK_MAKE_VERSION(0, 1, 0);   // 应用程序版本号
    ai.pEngineName = "opencolor";                       // 引擎名称
    ai.engineVersion = VK_MAKE_VERSION(0, 1, 0);        // 引擎版本号
    ai.apiVersion = VK_API_VERSION_1_1;                 // 使用的 Vulkan API 版本

    // 创建 Vulkan 实例
    VkInstanceCreateInfo ici{};
    ici.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO; // 结构体类型
    ici.pApplicationInfo = &ai;                         // 指向应用程序信息
    vk_check(vkCreateInstance(&ici, nullptr, &g_solver_vk_ctx.instance), "vkCreateInstance");

    // 枚举可用的物理设备（GPU）
    std::uint32_t device_count = 0;
    vk_check(vkEnumeratePhysicalDevices(g_solver_vk_ctx.instance, &device_count, nullptr), "vkEnumeratePhysicalDevices(count)");
    if (device_count == 0) {
        throw std::runtime_error("未找到 Vulkan 物理设备");
    }
    std::vector<VkPhysicalDevice> devices(device_count);
    vk_check(vkEnumeratePhysicalDevices(g_solver_vk_ctx.instance, &device_count, devices.data()), "vkEnumeratePhysicalDevices(list)");

    // 查找支持计算队列的物理设备
    for (auto pd : devices) {
        std::uint32_t qcount = 0;
        // 获取该物理设备的队列族属性
        vkGetPhysicalDeviceQueueFamilyProperties(pd, &qcount, nullptr);
        std::vector<VkQueueFamilyProperties> props(qcount);
        vkGetPhysicalDeviceQueueFamilyProperties(pd, &qcount, props.data());
        // 遍历队列族，查找支持计算的队列
        for (std::uint32_t i = 0; i < qcount; i++) {
            if (props[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
                g_solver_vk_ctx.physical_device = pd;   // 保存选中的物理设备
                g_solver_vk_ctx.queue_family = i;       // 保存队列族索引
                break;
            }
        }
        if (g_solver_vk_ctx.physical_device) {
            break;  // 找到合适的设备，退出循环
        }
    }

    // 如果没有找到支持计算的设备，抛出异常
    if (!g_solver_vk_ctx.physical_device) {
        throw std::runtime_error("未找到支持计算的 Vulkan 队列");
    }

    // 配置设备队列创建信息
    float qprio = 1.0f;                                 // 队列优先级（0.0 ~ 1.0）
    VkDeviceQueueCreateInfo qci{};
    qci.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO; // 结构体类型
    qci.queueFamilyIndex = g_solver_vk_ctx.queue_family;    // 队列族索引
    qci.queueCount = 1;                                 // 创建的队列数量
    qci.pQueuePriorities = &qprio;                      // 队列优先级数组

    // 创建逻辑设备
    VkDeviceCreateInfo dci{};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;   // 结构体类型
    dci.queueCreateInfoCount = 1;                       // 队列创建信息数量
    dci.pQueueCreateInfos = &qci;                       // 队列创建信息数组
    vk_check(vkCreateDevice(g_solver_vk_ctx.physical_device, &dci, nullptr, &g_solver_vk_ctx.device), "vkCreateDevice");
    // 获取设备队列句柄
    vkGetDeviceQueue(g_solver_vk_ctx.device, g_solver_vk_ctx.queue_family, 0, &g_solver_vk_ctx.queue);

    // 创建命令池，用于分配命令缓冲区
    VkCommandPoolCreateInfo cpci{};
    cpci.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;    // 结构体类型
    cpci.queueFamilyIndex = g_solver_vk_ctx.queue_family;       // 关联的队列族
    cpci.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT; // 允许重置命令缓冲区
    vk_check(vkCreateCommandPool(g_solver_vk_ctx.device, &cpci, nullptr, &g_solver_vk_ctx.command_pool), "vkCreateCommandPool");

    // 创建 RT slab 渲染管线（光线追踪 slab 计算管线）
    {
        // 编译 RT slab 计算着色器为 SPIR-V 字节码
        std::vector<std::uint32_t> spirv = compile_rt_slab_shader();

        // 创建着色器模块
        VkShaderModuleCreateInfo smci{};
        smci.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;   // 结构体类型
        smci.codeSize = spirv.size() * sizeof(std::uint32_t);       // SPIR-V 代码大小（字节）
        smci.pCode = spirv.data();                                  // SPIR-V 代码数据
        VkShaderModule shader = VK_NULL_HANDLE;
        vk_check(vkCreateShaderModule(g_solver_vk_ctx.device, &smci, nullptr, &shader), "vkCreateShaderModule");

        // 配置描述符集布局绑定（5 个存储缓冲区绑定）
        // 绑定 0：alpha 缓冲区
        VkDescriptorSetLayoutBinding b0{};
        b0.binding = 0;                                     // 绑定索引
        b0.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;  // 描述符类型：存储缓冲区
        b0.descriptorCount = 1;                             // 描述符数量
        b0.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;        // 使用阶段：计算着色器

        // 绑定 1-4：其他缓冲区（beta、gamma 等）
        VkDescriptorSetLayoutBinding b1 = b0;
        b1.binding = 1;
        VkDescriptorSetLayoutBinding b2 = b0;
        b2.binding = 2;
        VkDescriptorSetLayoutBinding b3 = b0;
        b3.binding = 3;
        VkDescriptorSetLayoutBinding b4 = b0;
        b4.binding = 4;

        // 创建描述符集布局
        VkDescriptorSetLayoutBinding bindings[5] = {b0, b1, b2, b3, b4};
        VkDescriptorSetLayoutCreateInfo dlci{};
        dlci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;   // 结构体类型
        dlci.bindingCount = 5;                              // 绑定数量
        dlci.pBindings = bindings;                          // 绑定数组
        vk_check(vkCreateDescriptorSetLayout(g_solver_vk_ctx.device, &dlci, nullptr, &g_solver_vk_ctx.desc_layout), "vkCreateDescriptorSetLayout");

        // 配置推送常量范围（用于传递小型 uniform 数据）
        VkPushConstantRange pcr{};
        pcr.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;       // 使用阶段：计算着色器
        pcr.offset = 0;                                     // 偏移量
        pcr.size = 32;                                      // 大小（字节）

        // 创建管线布局
        VkPipelineLayoutCreateInfo plci{};
        plci.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO; // 结构体类型
        plci.setLayoutCount = 1;                            // 描述符集布局数量
        plci.pSetLayouts = &g_solver_vk_ctx.desc_layout;    // 描述符集布局数组
        plci.pushConstantRangeCount = 1;                    // 推送常量范围数量
        plci.pPushConstantRanges = &pcr;                    // 推送常量范围数组
        vk_check(vkCreatePipelineLayout(g_solver_vk_ctx.device, &plci, nullptr, &g_solver_vk_ctx.pipeline_layout), "vkCreatePipelineLayout");

        // 配置计算管线着色器阶段
        VkPipelineShaderStageCreateInfo pssci{};
        pssci.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;  // 结构体类型
        pssci.stage = VK_SHADER_STAGE_COMPUTE_BIT;          // 着色器阶段：计算
        pssci.module = shader;                              // 着色器模块
        pssci.pName = "main";                               // 入口函数名称

        // 创建计算管线
        VkComputePipelineCreateInfo cpci2{};
        cpci2.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;   // 结构体类型
        cpci2.stage = pssci;                                // 着色器阶段配置
        cpci2.layout = g_solver_vk_ctx.pipeline_layout;     // 管线布局
        vk_check(vkCreateComputePipelines(g_solver_vk_ctx.device, VK_NULL_HANDLE, 1, &cpci2, nullptr, &g_solver_vk_ctx.pipeline), "vkCreateComputePipelines");

        // 销毁着色器模块（管线创建完成后不再需要）
        vkDestroyShaderModule(g_solver_vk_ctx.device, shader, nullptr);

        // 配置描述符池大小
        VkDescriptorPoolSize dps{};
        dps.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;       // 描述符类型
        dps.descriptorCount = 5;                            // 描述符数量

        // 创建描述符池
        VkDescriptorPoolCreateInfo dpci{};
        dpci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO; // 结构体类型
        dpci.maxSets = 1;                                   // 最大描述符集数量
        dpci.poolSizeCount = 1;                             // 池大小配置数量
        dpci.pPoolSizes = &dps;                             // 池大小配置数组
        vk_check(vkCreateDescriptorPool(g_solver_vk_ctx.device, &dpci, nullptr, &g_solver_vk_ctx.descriptor_pool), "vkCreateDescriptorPool");

        // 分配描述符集
        VkDescriptorSetAllocateInfo dsai{};
        dsai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;    // 结构体类型
        dsai.descriptorPool = g_solver_vk_ctx.descriptor_pool;          // 描述符池
        dsai.descriptorSetCount = 1;                        // 分配的描述符集数量
        dsai.pSetLayouts = &g_solver_vk_ctx.desc_layout;    // 描述符集布局数组
        vk_check(vkAllocateDescriptorSets(g_solver_vk_ctx.device, &dsai, &g_solver_vk_ctx.descriptor_set), "vkAllocateDescriptorSets");
    }

    // 创建 GPR 渲染管线（高斯过程回归计算管线）
    {
        // 编译 GPR 计算着色器为 SPIR-V 字节码
        std::vector<std::uint32_t> gpr_spv = compile_gpr_shader();

        // 创建着色器模块
        VkShaderModuleCreateInfo smci_gpr{};
        smci_gpr.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;   // 结构体类型
        smci_gpr.codeSize = gpr_spv.size() * sizeof(std::uint32_t);     // SPIR-V 代码大小
        smci_gpr.pCode = gpr_spv.data();                                // SPIR-V 代码数据
        VkShaderModule gpr_shader = VK_NULL_HANDLE;
        vk_check(vkCreateShaderModule(g_solver_vk_ctx.device, &smci_gpr, nullptr, &gpr_shader), "vkCreateShaderModule(gpr)");

        // 配置描述符集布局绑定（6 个存储缓冲区绑定）
        // 绑定 0：训练数据 X
        VkDescriptorSetLayoutBinding gb0{};
        gb0.binding = 0;
        gb0.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        gb0.descriptorCount = 1;
        gb0.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;

        // 绑定 1-5：其他 GPR 相关缓冲区
        VkDescriptorSetLayoutBinding gb1 = gb0;
        gb1.binding = 1;
        VkDescriptorSetLayoutBinding gb2 = gb0;
        gb2.binding = 2;
        VkDescriptorSetLayoutBinding gb3 = gb0;
        gb3.binding = 3;
        VkDescriptorSetLayoutBinding gb4 = gb0;
        gb4.binding = 4;
        VkDescriptorSetLayoutBinding gb5 = gb0;
        gb5.binding = 5;

        // 创建 GPR 描述符集布局
        VkDescriptorSetLayoutBinding gbindings[6] = {gb0, gb1, gb2, gb3, gb4, gb5};
        VkDescriptorSetLayoutCreateInfo gdlci{};
        gdlci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
        gdlci.bindingCount = 6;
        gdlci.pBindings = gbindings;
        vk_check(vkCreateDescriptorSetLayout(g_solver_vk_ctx.device, &gdlci, nullptr, &g_solver_vk_ctx.gpr_desc_layout), "vkCreateDescriptorSetLayout(gpr)");

        // 配置 GPR 推送常量范围
        VkPushConstantRange gpcr{};
        gpcr.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
        gpcr.offset = 0;
        gpcr.size = 80;                                     // GPR 需要更大的推送常量空间

        // 创建 GPR 管线布局
        VkPipelineLayoutCreateInfo gplci{};
        gplci.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
        gplci.setLayoutCount = 1;
        gplci.pSetLayouts = &g_solver_vk_ctx.gpr_desc_layout;
        gplci.pushConstantRangeCount = 1;
        gplci.pPushConstantRanges = &gpcr;
        vk_check(vkCreatePipelineLayout(g_solver_vk_ctx.device, &gplci, nullptr, &g_solver_vk_ctx.gpr_pipeline_layout), "vkCreatePipelineLayout(gpr)");

        // 配置 GPR 计算管线着色器阶段
        VkPipelineShaderStageCreateInfo gpssci{};
        gpssci.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
        gpssci.stage = VK_SHADER_STAGE_COMPUTE_BIT;
        gpssci.module = gpr_shader;
        gpssci.pName = "main";

        // 创建 GPR 计算管线
        VkComputePipelineCreateInfo gcpci{};
        gcpci.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
        gcpci.stage = gpssci;
        gcpci.layout = g_solver_vk_ctx.gpr_pipeline_layout;
        vk_check(vkCreateComputePipelines(g_solver_vk_ctx.device, VK_NULL_HANDLE, 1, &gcpci, nullptr, &g_solver_vk_ctx.gpr_pipeline), "vkCreateComputePipelines(gpr)");

        // 销毁 GPR 着色器模块
        vkDestroyShaderModule(g_solver_vk_ctx.device, gpr_shader, nullptr);

        // 配置 GPR 描述符池大小
        VkDescriptorPoolSize gdps{};
        gdps.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        gdps.descriptorCount = 6;

        // 创建 GPR 描述符池
        VkDescriptorPoolCreateInfo gdpci{};
        gdpci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        gdpci.maxSets = 1;
        gdpci.poolSizeCount = 1;
        gdpci.pPoolSizes = &gdps;
        vk_check(vkCreateDescriptorPool(g_solver_vk_ctx.device, &gdpci, nullptr, &g_solver_vk_ctx.gpr_descriptor_pool), "vkCreateDescriptorPool(gpr)");

        // 分配 GPR 描述符集
        VkDescriptorSetAllocateInfo gdsai{};
        gdsai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        gdsai.descriptorPool = g_solver_vk_ctx.gpr_descriptor_pool;
        gdsai.descriptorSetCount = 1;
        gdsai.pSetLayouts = &g_solver_vk_ctx.gpr_desc_layout;
        vk_check(vkAllocateDescriptorSets(g_solver_vk_ctx.device, &gdsai, &g_solver_vk_ctx.gpr_descriptor_set), "vkAllocateDescriptorSets(gpr)");
    }

    // 标记 Vulkan 上下文初始化完成
    g_solver_vk_ready = true;
}

// 销毁求解器 Vulkan 上下文
// 按相反顺序释放所有 Vulkan 资源
void destroy_solver_vulkan_context() {
    std::lock_guard<std::mutex> lock(g_solver_vk_mutex);
    // 如果未初始化，直接返回
    if (!g_solver_vk_ready) {
        return;
    }
    // 如果设备句柄无效，只重置状态
    if (!g_solver_vk_ctx.device) {
        g_solver_vk_ready = false;
        return;
    }

    // 等待设备完成所有队列操作
    vkDeviceWaitIdle(g_solver_vk_ctx.device);

    // 销毁 GPR 相关资源（按创建顺序的逆序）
    // 销毁 GPR 描述符池
    if (g_solver_vk_ctx.gpr_descriptor_pool) {
        vkDestroyDescriptorPool(g_solver_vk_ctx.device, g_solver_vk_ctx.gpr_descriptor_pool, nullptr);
        g_solver_vk_ctx.gpr_descriptor_pool = VK_NULL_HANDLE;
    }
    // 销毁 GPR 计算管线
    if (g_solver_vk_ctx.gpr_pipeline) {
        vkDestroyPipeline(g_solver_vk_ctx.device, g_solver_vk_ctx.gpr_pipeline, nullptr);
        g_solver_vk_ctx.gpr_pipeline = VK_NULL_HANDLE;
    }
    // 销毁 GPR 管线布局
    if (g_solver_vk_ctx.gpr_pipeline_layout) {
        vkDestroyPipelineLayout(g_solver_vk_ctx.device, g_solver_vk_ctx.gpr_pipeline_layout, nullptr);
        g_solver_vk_ctx.gpr_pipeline_layout = VK_NULL_HANDLE;
    }
    // 销毁 GPR 描述符集布局
    if (g_solver_vk_ctx.gpr_desc_layout) {
        vkDestroyDescriptorSetLayout(g_solver_vk_ctx.device, g_solver_vk_ctx.gpr_desc_layout, nullptr);
        g_solver_vk_ctx.gpr_desc_layout = VK_NULL_HANDLE;
    }

    // 销毁 RT slab 相关资源
    // 销毁描述符池
    if (g_solver_vk_ctx.descriptor_pool) {
        vkDestroyDescriptorPool(g_solver_vk_ctx.device, g_solver_vk_ctx.descriptor_pool, nullptr);
        g_solver_vk_ctx.descriptor_pool = VK_NULL_HANDLE;
    }
    // 销毁计算管线
    if (g_solver_vk_ctx.pipeline) {
        vkDestroyPipeline(g_solver_vk_ctx.device, g_solver_vk_ctx.pipeline, nullptr);
        g_solver_vk_ctx.pipeline = VK_NULL_HANDLE;
    }
    // 销毁管线布局
    if (g_solver_vk_ctx.pipeline_layout) {
        vkDestroyPipelineLayout(g_solver_vk_ctx.device, g_solver_vk_ctx.pipeline_layout, nullptr);
        g_solver_vk_ctx.pipeline_layout = VK_NULL_HANDLE;
    }
    // 销毁描述符集布局
    if (g_solver_vk_ctx.desc_layout) {
        vkDestroyDescriptorSetLayout(g_solver_vk_ctx.device, g_solver_vk_ctx.desc_layout, nullptr);
        g_solver_vk_ctx.desc_layout = VK_NULL_HANDLE;
    }

    // 销毁命令池
    if (g_solver_vk_ctx.command_pool) {
        vkDestroyCommandPool(g_solver_vk_ctx.device, g_solver_vk_ctx.command_pool, nullptr);
        g_solver_vk_ctx.command_pool = VK_NULL_HANDLE;
    }

    // 销毁逻辑设备
    vkDestroyDevice(g_solver_vk_ctx.device, nullptr);
    g_solver_vk_ctx.device = VK_NULL_HANDLE;
    g_solver_vk_ctx.queue = VK_NULL_HANDLE;
    g_solver_vk_ctx.physical_device = VK_NULL_HANDLE;

    // 销毁 Vulkan 实例
    if (g_solver_vk_ctx.instance) {
        vkDestroyInstance(g_solver_vk_ctx.instance, nullptr);
        g_solver_vk_ctx.instance = VK_NULL_HANDLE;
    }
    // 重置就绪状态
    g_solver_vk_ready = false;
}

// HillClimbingSolverVulkanState 析构函数
// 自动释放该求解器状态占用的 Vulkan 缓冲区资源
HillClimbingSolverVulkanState::~HillClimbingSolverVulkanState() {
    // 如果 Vulkan 上下文未就绪或设备无效，跳过清理
    if (!g_solver_vk_ready || !g_solver_vk_ctx.device) {
        return;
    }
    // 销毁 RT slab 相关的缓冲区
    destroy_buffer(g_solver_vk_ctx.device, alpha);
    destroy_buffer(g_solver_vk_ctx.device, beta);
    destroy_buffer(g_solver_vk_ctx.device, gamma);
    uploaded_rts = false;   // 重置 RT slab 上传标志

    // 销毁 GPR 相关的缓冲区
    destroy_buffer(g_solver_vk_ctx.device, gpr_X_train);
    destroy_buffer(g_solver_vk_ctx.device, gpr_alpha_L);
    destroy_buffer(g_solver_vk_ctx.device, gpr_alpha_a);
    destroy_buffer(g_solver_vk_ctx.device, gpr_alpha_b);
    uploaded_gpr = false;   // 重置 GPR 上传标志
}

} // namespace solver
} // namespace opencolor
