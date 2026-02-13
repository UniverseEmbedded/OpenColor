#include <chrono>
#include <iostream>
#include <string>
#include <vector>

// Vulkan 头文件
#include <vulkan/vulkan.h>

/**
 * 对字符串进行 JSON 转义
 * @param input 原始字符串
 * @return 转义后的字符串，可安全用于 JSON 值
 */
static std::string json_escape(const std::string& input)
{
    std::string out;
    out.reserve(input.size());
    for (const char c : input) {
        switch (c) {
        case '"':
            out += "\\\"";  // 双引号转义
            break;
        case '\\':
            out += "\\\\";  // 反斜杠转义
            break;
        case '\n':
            out += "\\n";   // 换行符转义
            break;
        case '\r':
            out += "\\r";   // 回车符转义
            break;
        case '\t':
            out += "\\t";   // 制表符转义
            break;
        default:
            out += c;
            break;
        }
    }
    return out;
}

/**
 * 检测可用的 Vulkan 计算设备
 * @return JSON 格式的 GPU 检测结果
 */
static std::string check_gpu_availability()
{
    // 初始化 Vulkan 实例
    VkApplicationInfo app_info{};
    app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app_info.pApplicationName = "opencolor_gpu_check";
    app_info.applicationVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.pEngineName = "opencolor";
    app_info.engineVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.apiVersion = VK_API_VERSION_1_1;

    VkInstanceCreateInfo create_info{};
    create_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create_info.pApplicationInfo = &app_info;

    VkInstance instance;
    VkResult result = vkCreateInstance(&create_info, nullptr, &instance);
    
    if (result != VK_SUCCESS) {
        return "{\"available\":false,\"device_count\":0,\"device_names\":[],\"message\":\"无法创建 Vulkan 实例\"}";
    }

    // 枚举物理设备
    uint32_t device_count = 0;
    result = vkEnumeratePhysicalDevices(instance, &device_count, nullptr);
    
    if (result != VK_SUCCESS || device_count == 0) {
        vkDestroyInstance(instance, nullptr);
        return "{\"available\":false,\"device_count\":0,\"device_names\":[],\"message\":\"未找到 Vulkan 设备\"}";
    }

    std::vector<VkPhysicalDevice> devices(device_count);
    vkEnumeratePhysicalDevices(instance, &device_count, devices.data());

    // 收集支持计算的设备信息
    std::vector<std::string> device_names;
    uint32_t compute_device_count = 0;

    for (auto device : devices) {
        // 获取设备属性
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(device, &props);

        // 检查是否支持计算队列
        uint32_t queue_family_count = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(device, &queue_family_count, nullptr);
        
        if (queue_family_count == 0) {
            continue;
        }

        std::vector<VkQueueFamilyProperties> queue_families(queue_family_count);
        vkGetPhysicalDeviceQueueFamilyProperties(device, &queue_family_count, queue_families.data());

        // 查找支持计算的队列族
        bool supports_compute = false;
        for (const auto& family : queue_families) {
            if (family.queueFlags & VK_QUEUE_COMPUTE_BIT) {
                supports_compute = true;
                break;
            }
        }

        if (supports_compute) {
            compute_device_count++;
            device_names.push_back(json_escape(props.deviceName));
        }
    }

    vkDestroyInstance(instance, nullptr);

    // 构建 JSON 响应
    std::string json = "{\"available\":" + std::string(compute_device_count > 0 ? "true" : "false");
    json += ",\"device_count\":" + std::to_string(compute_device_count);
    json += ",\"device_names\":[";
    
    for (size_t i = 0; i < device_names.size(); i++) {
        if (i > 0) json += ",";
        json += "\"" + device_names[i] + "\"";
    }
    
    json += "],\"message\":\"";
    if (compute_device_count > 0) {
        json += "检测到 " + std::to_string(compute_device_count) + " 个支持 Vulkan 计算的设备";
    } else {
        json += "未找到支持 Vulkan 计算的设备";
    }
    json += "\"}";

    return json;
}

/**
 * Web 探测程序入口
 * 解析命令行参数，输出 JSON 格式的连接确认信息
 */
int main(int argc, char** argv)
{
    // 检查是否是 GPU 检测模式
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--check-gpu") {
            // 执行 GPU 检测并输出结果
            std::cout << check_gpu_availability() << std::endl;
            return 0;
        }
    }

    // 解析命令行参数，支持 --payload 或 -p 选项
    std::string payload;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--payload" || arg == "-p") {
            if (i + 1 < argc) {
                payload = argv[i + 1];
                ++i;
            }
            continue;
        }
        if (arg.rfind("--payload=", 0) == 0) {
            payload = arg.substr(10);
            continue;
        }
        if (!payload.empty()) {
            payload += " ";
        }
        payload += arg;
    }

    // 获取当前时间戳（毫秒）
    const auto now = std::chrono::system_clock::now();
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
    const std::string safe_payload = json_escape(payload);

    // 输出 JSON 格式的连接确认信息
    std::cout << "{\"ok\":true,\"message\":\"C++ 模块已连接\",\"payload\":\"" << safe_payload
              << "\",\"ts_ms\":" << ms << "}" << std::endl;
    return 0;
}
