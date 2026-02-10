#include "vulkan_init.h"
#include <vector>
#include <cstdio>
#include <cstdlib>

VkFormat choose_surface_format(const std::vector<VkSurfaceFormatKHR>& formats)
{
    for (const auto& f : formats) {
        if (f.format == VK_FORMAT_B8G8R8A8_UNORM && f.colorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
            return f.format;
        }
        if (f.format == VK_FORMAT_R8G8B8A8_UNORM && f.colorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
            return f.format;
        }
    }
    return formats.empty() ? VK_FORMAT_B8G8R8A8_UNORM : formats[0].format;
}

VkPresentModeKHR choose_present_mode(const std::vector<VkPresentModeKHR>& modes)
{
    for (auto m : modes) {
        if (m == VK_PRESENT_MODE_MAILBOX_KHR) {
            return m;
        }
    }
    return VK_PRESENT_MODE_FIFO_KHR;
}

VkExtent2D clamp_extent(const VkSurfaceCapabilitiesKHR& caps, std::uint32_t w, std::uint32_t h)
{
    VkExtent2D e{};
    if (caps.currentExtent.width != UINT32_MAX) {
        return caps.currentExtent;
    }
    e.width = w;
    e.height = h;
    if (e.width < caps.minImageExtent.width) e.width = caps.minImageExtent.width;
    if (e.width > caps.minImageExtent.width) e.width = caps.maxImageExtent.width;
    if (e.height < caps.minImageExtent.height) e.height = caps.minImageExtent.height;
    if (e.height > caps.maxImageExtent.height) e.height = caps.maxImageExtent.height;
    return e;
}

void create_instance(AppVulkan& app)
{
    std::vector<const char*> extensions;
    // 由于 SDL3 已移除，这里不再自动获取 SDL 的 Vulkan 扩展
    // 如果需要显存渲染或窗口显示，需要手动添加扩展，例如 VK_KHR_SURFACE
    
    VkApplicationInfo app_info{};
    app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app_info.pApplicationName = "OpenColor C++ Demo";
    app_info.applicationVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.pEngineName = "opencolor";
    app_info.engineVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.apiVersion = VK_API_VERSION_1_1;

    VkInstanceCreateInfo ci{};
    ci.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo = &app_info;
    ci.enabledExtensionCount = static_cast<std::uint32_t>(extensions.size());
    ci.ppEnabledExtensionNames = extensions.data();

    vk_check(vkCreateInstance(&ci, nullptr, &app.instance), "vkCreateInstance");
}

void create_surface(AppVulkan& app)
{
    // 由于 SDL3 已移除，无法再创建 SDL 表面
    // 这里暂时留空或抛出错误，取决于后续如何使用
    std::fprintf(stderr, "[警告] SDL3 已移除，无法创建 Vulkan 表面\n");
}

void pick_physical_device_and_queue(AppVulkan& app)
{
    std::uint32_t device_count = 0;
    vk_check(vkEnumeratePhysicalDevices(app.instance, &device_count, nullptr), "vkEnumeratePhysicalDevices(count)");
    if (device_count == 0) {
        std::fprintf(stderr, "[错误] 未找到 Vulkan 物理设备\n");
        std::abort();
    }
    std::vector<VkPhysicalDevice> devices(device_count);
    vk_check(vkEnumeratePhysicalDevices(app.instance, &device_count, devices.data()), "vkEnumeratePhysicalDevices(list)");

    for (auto pd : devices) {
        std::uint32_t qcount = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(pd, &qcount, nullptr);
        std::vector<VkQueueFamilyProperties> qprops(qcount);
        vkGetPhysicalDeviceQueueFamilyProperties(pd, &qcount, qprops.data());

        for (std::uint32_t i = 0; i < qcount; i++) {
            if ((qprops[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) == 0) {
                continue;
            }
            
            // 如果存在表面，检查是否支持呈现
            if (app.surface) {
                VkBool32 present_support = VK_FALSE;
                vk_check(vkGetPhysicalDeviceSurfaceSupportKHR(pd, i, app.surface, &present_support), "vkGetPhysicalDeviceSurfaceSupportKHR");
                if (!present_support) {
                    continue;
                }
            }
            
            app.physical_device = pd;
            app.queue_family = i;
            return;
        }
    }

    std::fprintf(stderr, "[错误] 未找到合适的队列族\n");
    std::abort();
}

void create_device(AppVulkan& app)
{
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci{};
    qci.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qci.queueFamilyIndex = app.queue_family;
    qci.queueCount = 1;
    qci.pQueuePriorities = &prio;

    const char* exts[] = { VK_KHR_SWAPCHAIN_EXTENSION_NAME };
    VkDeviceCreateInfo dci{};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;
    dci.enabledExtensionCount = 1;
    dci.ppEnabledExtensionNames = exts;

    vk_check(vkCreateDevice(app.physical_device, &dci, nullptr, &app.device), "vkCreateDevice");
    vkGetDeviceQueue(app.device, app.queue_family, 0, &app.queue);
}

void create_swapchain(AppVulkan& app)
{
    if (!app.surface) {
        std::fprintf(stderr, "[警告] 无有效表面，跳过交换链创建\n");
        return;
    }
    VkSurfaceCapabilitiesKHR caps{};
    vk_check(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(app.physical_device, app.surface, &caps), "vkGetPhysicalDeviceSurfaceCapabilitiesKHR");

    std::uint32_t fmt_count = 0;
    vk_check(vkGetPhysicalDeviceSurfaceFormatsKHR(app.physical_device, app.surface, &fmt_count, nullptr), "vkGetPhysicalDeviceSurfaceFormatsKHR(count)");
    std::vector<VkSurfaceFormatKHR> formats(fmt_count);
    vk_check(vkGetPhysicalDeviceSurfaceFormatsKHR(app.physical_device, app.surface, &fmt_count, formats.data()), "vkGetPhysicalDeviceSurfaceFormatsKHR(list)");

    std::uint32_t pm_count = 0;
    vk_check(vkGetPhysicalDeviceSurfacePresentModesKHR(app.physical_device, app.surface, &pm_count, nullptr), "vkGetPhysicalDeviceSurfacePresentModesKHR(count)");
    std::vector<VkPresentModeKHR> present_modes(pm_count);
    vk_check(vkGetPhysicalDeviceSurfacePresentModesKHR(app.physical_device, app.surface, &pm_count, present_modes.data()), "vkGetPhysicalDeviceSurfacePresentModesKHR(list)");

    int ww = 1280;
    int wh = 720;
    // SDL_GetWindowSize 已移除
    int dw = ww;
    int dh = wh;
    // SDL_GetWindowSizeInPixels 已移除

    VkFormat format = choose_surface_format(formats);
    VkPresentModeKHR present_mode = choose_present_mode(present_modes);
    VkExtent2D extent = clamp_extent(caps, static_cast<std::uint32_t>(dw), static_cast<std::uint32_t>(dh));

    std::uint32_t image_count = caps.minImageCount + 1;
    if (caps.maxImageCount > 0 && image_count > caps.maxImageCount) {
        image_count = caps.maxImageCount;
    }

    VkSwapchainCreateInfoKHR sci{};
    sci.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
    sci.surface = app.surface;
    sci.minImageCount = image_count;
    sci.imageFormat = format;
    sci.imageColorSpace = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
    sci.imageExtent = extent;
    sci.imageArrayLayers = 1;
    sci.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    sci.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
    sci.preTransform = caps.currentTransform;
    sci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    sci.presentMode = present_mode;
    sci.clipped = VK_TRUE;

    vk_check(vkCreateSwapchainKHR(app.device, &sci, nullptr, &app.swapchain), "vkCreateSwapchainKHR");
    app.swapchain_format = format;
    app.swapchain_extent = extent;

    std::uint32_t out_count = 0;
    vk_check(vkGetSwapchainImagesKHR(app.device, app.swapchain, &out_count, nullptr), "vkGetSwapchainImagesKHR(count)");
    app.swapchain_images.resize(out_count);
    vk_check(vkGetSwapchainImagesKHR(app.device, app.swapchain, &out_count, app.swapchain_images.data()), "vkGetSwapchainImagesKHR(list)");

    app.swapchain_image_views.resize(out_count);
    for (std::uint32_t i = 0; i < out_count; i++) {
        VkImageViewCreateInfo vci{};
        vci.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        vci.image = app.swapchain_images[i];
        vci.viewType = VK_IMAGE_VIEW_TYPE_2D;
        vci.format = app.swapchain_format;
        vci.components.r = VK_COMPONENT_SWIZZLE_IDENTITY;
        vci.components.g = VK_COMPONENT_SWIZZLE_IDENTITY;
        vci.components.b = VK_COMPONENT_SWIZZLE_IDENTITY;
        vci.components.a = VK_COMPONENT_SWIZZLE_IDENTITY;
        vci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        vci.subresourceRange.baseMipLevel = 0;
        vci.subresourceRange.levelCount = 1;
        vci.subresourceRange.baseArrayLayer = 0;
        vci.subresourceRange.layerCount = 1;
        vk_check(vkCreateImageView(app.device, &vci, nullptr, &app.swapchain_image_views[i]), "vkCreateImageView");
    }
}

void create_render_pass(AppVulkan& app)
{
    VkAttachmentDescription color{};
    color.format = app.swapchain_format;
    color.samples = VK_SAMPLE_COUNT_1_BIT;
    color.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    color.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    color.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    color.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    color.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    color.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;

    VkAttachmentReference color_ref{};
    color_ref.attachment = 0;
    color_ref.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1;
    subpass.pColorAttachments = &color_ref;

    VkSubpassDependency dep{};
    dep.srcSubpass = VK_SUBPASS_EXTERNAL;
    dep.dstSubpass = 0;
    dep.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dep.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dep.srcAccessMask = 0;
    dep.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;

    VkRenderPassCreateInfo rpci{};
    rpci.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
    rpci.attachmentCount = 1;
    rpci.pAttachments = &color;
    rpci.subpassCount = 1;
    rpci.pSubpasses = &subpass;
    rpci.dependencyCount = 1;
    rpci.pDependencies = &dep;

    vk_check(vkCreateRenderPass(app.device, &rpci, nullptr, &app.render_pass), "vkCreateRenderPass");
}

void create_framebuffers(AppVulkan& app)
{
    app.framebuffers.resize(app.swapchain_image_views.size());
    for (std::size_t i = 0; i < app.swapchain_image_views.size(); i++) {
        VkImageView attachments[] = { app.swapchain_image_views[i] };
        VkFramebufferCreateInfo fci{};
        fci.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        fci.renderPass = app.render_pass;
        fci.attachmentCount = 1;
        fci.pAttachments = attachments;
        fci.width = app.swapchain_extent.width;
        fci.height = app.swapchain_extent.height;
        fci.layers = 1;
        vk_check(vkCreateFramebuffer(app.device, &fci, nullptr, &app.framebuffers[i]), "vkCreateFramebuffer");
    }
}

void create_command_pool_and_buffers(AppVulkan& app)
{
    VkCommandPoolCreateInfo cpci{};
    cpci.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    cpci.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    cpci.queueFamilyIndex = app.queue_family;
    vk_check(vkCreateCommandPool(app.device, &cpci, nullptr, &app.command_pool), "vkCreateCommandPool");

    app.command_buffers.resize(app.framebuffers.size());
    VkCommandBufferAllocateInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    ai.commandPool = app.command_pool;
    ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount = static_cast<std::uint32_t>(app.command_buffers.size());
    vk_check(vkAllocateCommandBuffers(app.device, &ai, app.command_buffers.data()), "vkAllocateCommandBuffers");
}

void create_sync_objects(AppVulkan& app)
{
    VkSemaphoreCreateInfo sci{};
    sci.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

    VkFenceCreateInfo fci{};
    fci.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    fci.flags = VK_FENCE_CREATE_SIGNALED_BIT;

    for (int i = 0; i < AppVulkan::MaxFramesInFlight; i++) {
        vk_check(vkCreateSemaphore(app.device, &sci, nullptr, &app.image_acquired_semaphores[i]), "vkCreateSemaphore(image_acquired)");
        vk_check(vkCreateSemaphore(app.device, &sci, nullptr, &app.render_complete_semaphores[i]), "vkCreateSemaphore(render_complete)");
        vk_check(vkCreateFence(app.device, &fci, nullptr, &app.in_flight_fences[i]), "vkCreateFence");
    }
}

void create_imgui_descriptor_pool(AppVulkan& app)
{
    VkDescriptorPoolSize pool_sizes[] = {
        { VK_DESCRIPTOR_TYPE_SAMPLER, 1000 },
        { VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1000 },
        { VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC, 1000 },
        { VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT, 1000 },
    };

    VkDescriptorPoolCreateInfo dpci{};
    dpci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    dpci.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
    dpci.maxSets = 1000 * static_cast<std::uint32_t>(std::size(pool_sizes));
    dpci.poolSizeCount = static_cast<std::uint32_t>(std::size(pool_sizes));
    dpci.pPoolSizes = pool_sizes;
    vk_check(vkCreateDescriptorPool(app.device, &dpci, nullptr, &app.imgui_descriptor_pool), "vkCreateDescriptorPool");
}

VkCommandBuffer begin_one_time_commands(AppVulkan& app)
{
    VkCommandBufferAllocateInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    ai.commandPool = app.command_pool;
    ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount = 1;

    VkCommandBuffer cmd{};
    vk_check(vkAllocateCommandBuffers(app.device, &ai, &cmd), "vkAllocateCommandBuffers(one_time)");

    VkCommandBufferBeginInfo bi{};
    bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vk_check(vkBeginCommandBuffer(cmd, &bi), "vkBeginCommandBuffer(one_time)");
    return cmd;
}

void end_one_time_commands(AppVulkan& app, VkCommandBuffer cmd)
{
    vk_check(vkEndCommandBuffer(cmd), "vkEndCommandBuffer(one_time)");

    VkSubmitInfo si{};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cmd;
    vk_check(vkQueueSubmit(app.queue, 1, &si, VK_NULL_HANDLE), "vkQueueSubmit(one_time)");
    vk_check(vkQueueWaitIdle(app.queue), "vkQueueWaitIdle(one_time)");
    vkFreeCommandBuffers(app.device, app.command_pool, 1, &cmd);
}
