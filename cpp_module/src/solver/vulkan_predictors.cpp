#include "vulkan_predictors.h"
#include "vulkan_context.h"
#include "vulkan_buffer.h"
#include "vulkan_utils.h"
#include "hill_climbing_solver.h"
#include <cstring>
#include <vector>

namespace opencolor {
namespace solver {

// RT Slab Vulkan 预测器内部实现
std::vector<float> predict_rt_slab_vulkan_internal(
    const std::vector<int32_t>& sequences,
    int n_seq,
    int n_layers,
    int num_materials,
    const OpticalParams& optical,
    const std::string& layer_names_order,
    HillClimbingSolverVulkanState* vk_state
) {
    if (!is_solver_vulkan_ready()) {
        throw std::runtime_error("Vulkan 上下文未初始化");
    }

    std::lock_guard<std::mutex> lock(get_solver_vulkan_mutex());
    SolverVulkanContext& vk_ctx = get_solver_vulkan_context();

    // 确保 RT slab 数据已上传
    if (!vk_state->uploaded_rts) {
        std::size_t alpha_needed = static_cast<std::size_t>(num_materials) * 3u * sizeof(float);
        std::size_t beta_needed = static_cast<std::size_t>(num_materials) * 3u * sizeof(float);
        std::size_t gamma_needed = 3u * sizeof(float);

        if (vk_state->alpha_bytes < alpha_needed) {
            destroy_buffer(vk_ctx.device, vk_state->alpha);
            vk_state->alpha = create_buffer(vk_ctx.device, vk_ctx.physical_device, alpha_needed, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->alpha_bytes = alpha_needed;
        }
        if (vk_state->beta_bytes < beta_needed) {
            destroy_buffer(vk_ctx.device, vk_state->beta);
            vk_state->beta = create_buffer(vk_ctx.device, vk_ctx.physical_device, beta_needed, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->beta_bytes = beta_needed;
        }
        if (vk_state->gamma_bytes < gamma_needed) {
            destroy_buffer(vk_ctx.device, vk_state->gamma);
            vk_state->gamma = create_buffer(vk_ctx.device, vk_ctx.physical_device, gamma_needed, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->gamma_bytes = gamma_needed;
        }

        void* ptr = nullptr;
        vk_check(vkMapMemory(vk_ctx.device, vk_state->alpha.memory, 0, alpha_needed, 0, &ptr), "vkMapMemory(alpha)");
        std::memcpy(ptr, optical.alpha.data(), alpha_needed);
        vkUnmapMemory(vk_ctx.device, vk_state->alpha.memory);

        vk_check(vkMapMemory(vk_ctx.device, vk_state->beta.memory, 0, beta_needed, 0, &ptr), "vkMapMemory(beta)");
        std::memcpy(ptr, optical.beta.data(), beta_needed);
        vkUnmapMemory(vk_ctx.device, vk_state->beta.memory);

        vk_check(vkMapMemory(vk_ctx.device, vk_state->gamma.memory, 0, gamma_needed, 0, &ptr), "vkMapMemory(gamma)");
        std::memcpy(ptr, optical.gamma.data(), gamma_needed);
        vkUnmapMemory(vk_ctx.device, vk_state->gamma.memory);

        vk_state->num_mats = static_cast<std::uint32_t>(num_materials);
        vk_state->uploaded_rts = true;
    }

    // 创建序列缓冲区
    std::size_t seq_bytes = static_cast<std::size_t>(n_seq) * static_cast<std::size_t>(n_layers) * sizeof(int32_t);
    VulkanBuffer seq_buf = create_buffer(vk_ctx.device, vk_ctx.physical_device, seq_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
    ScopedVulkanBuffer seq_guard(vk_ctx.device, seq_buf);

    void* ptr = nullptr;
    vk_check(vkMapMemory(vk_ctx.device, seq_buf.memory, 0, seq_bytes, 0, &ptr), "vkMapMemory(seq)");
    std::memcpy(ptr, sequences.data(), seq_bytes);
    vkUnmapMemory(vk_ctx.device, seq_buf.memory);

    // 创建输出缓冲区
    std::size_t out_bytes = static_cast<std::size_t>(n_seq) * 3u * sizeof(float);
    VulkanBuffer out_buf = create_buffer(vk_ctx.device, vk_ctx.physical_device, out_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
    ScopedVulkanBuffer out_guard(vk_ctx.device, out_buf);

    // 更新描述符集
    VkDescriptorBufferInfo alpha_info{};
    alpha_info.buffer = vk_state->alpha.buffer;
    alpha_info.offset = 0;
    alpha_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo beta_info{};
    beta_info.buffer = vk_state->beta.buffer;
    beta_info.offset = 0;
    beta_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo gamma_info{};
    gamma_info.buffer = vk_state->gamma.buffer;
    gamma_info.offset = 0;
    gamma_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo seq_info{};
    seq_info.buffer = seq_buf.buffer;
    seq_info.offset = 0;
    seq_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo out_info{};
    out_info.buffer = out_buf.buffer;
    out_info.offset = 0;
    out_info.range = VK_WHOLE_SIZE;

    VkWriteDescriptorSet writes[5] = {};

    writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[0].dstSet = vk_ctx.descriptor_set;
    writes[0].dstBinding = 0;
    writes[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[0].descriptorCount = 1;
    writes[0].pBufferInfo = &alpha_info;

    writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[1].dstSet = vk_ctx.descriptor_set;
    writes[1].dstBinding = 1;
    writes[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[1].descriptorCount = 1;
    writes[1].pBufferInfo = &beta_info;

    writes[2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[2].dstSet = vk_ctx.descriptor_set;
    writes[2].dstBinding = 2;
    writes[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[2].descriptorCount = 1;
    writes[2].pBufferInfo = &gamma_info;

    writes[3].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[3].dstSet = vk_ctx.descriptor_set;
    writes[3].dstBinding = 3;
    writes[3].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[3].descriptorCount = 1;
    writes[3].pBufferInfo = &seq_info;

    writes[4].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[4].dstSet = vk_ctx.descriptor_set;
    writes[4].dstBinding = 4;
    writes[4].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[4].descriptorCount = 1;
    writes[4].pBufferInfo = &out_info;

    vkUpdateDescriptorSets(vk_ctx.device, 5, writes, 0, nullptr);

    // 分配命令缓冲区
    VkCommandBufferAllocateInfo cbai{};
    cbai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cbai.commandPool = vk_ctx.command_pool;
    cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cbai.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    vk_check(vkAllocateCommandBuffers(vk_ctx.device, &cbai, &cmd), "vkAllocateCommandBuffers");
    ScopedCommandBuffer cmd_guard(vk_ctx.device, vk_ctx.command_pool, cmd);

    // 记录命令
    VkCommandBufferBeginInfo cbbi{};
    cbbi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    cbbi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vk_check(vkBeginCommandBuffer(cmd, &cbbi), "vkBeginCommandBuffer");

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, vk_ctx.pipeline);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, vk_ctx.pipeline_layout, 0, 1, &vk_ctx.descriptor_set, 0, nullptr);

    struct PushConstants {
        std::uint32_t num_seq;
        std::uint32_t n_layers;
        std::uint32_t layer_order;
        std::uint32_t num_mats;
        float pad0;
        float pad1;
        float pad2;
    } pc;

    pc.num_seq = static_cast<std::uint32_t>(n_seq);
    pc.n_layers = static_cast<std::uint32_t>(n_layers);
    pc.layer_order = (layer_names_order == "bottom_first") ? 0u : 1u;
    pc.num_mats = vk_state->num_mats;
    pc.pad0 = pc.pad1 = pc.pad2 = 0.0f;

    vkCmdPushConstants(cmd, vk_ctx.pipeline_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);

    std::uint32_t total_invocations = static_cast<std::uint32_t>(n_seq) * 3u;
    std::uint32_t group_count = (total_invocations + 255u) / 256u;
    vkCmdDispatch(cmd, group_count, 1, 1);

    vk_check(vkEndCommandBuffer(cmd), "vkEndCommandBuffer");

    // 提交命令
    VkSubmitInfo si{};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cmd;
    vk_check(vkQueueSubmit(vk_ctx.queue, 1, &si, VK_NULL_HANDLE), "vkQueueSubmit");
    vk_check(vkQueueWaitIdle(vk_ctx.queue), "vkQueueWaitIdle");

    // 读取结果
    std::vector<float> result(static_cast<std::size_t>(n_seq) * 3u);
    vk_check(vkMapMemory(vk_ctx.device, out_buf.memory, 0, out_bytes, 0, &ptr), "vkMapMemory(out)");
    std::memcpy(result.data(), ptr, out_bytes);
    vkUnmapMemory(vk_ctx.device, out_buf.memory);

    return result;
}

// GPR Vulkan 预测器内部实现
std::vector<float> predict_gpr_vulkan3_internal(
    const std::vector<float>& X,
    int n_samples,
    HillClimbingSolverVulkanState* vk_state,
    const GPRParams& gL,
    const GPRParams& ga,
    const GPRParams& gb
) {
    if (!is_solver_vulkan_ready()) {
        throw std::runtime_error("Vulkan 上下文未初始化");
    }

    std::lock_guard<std::mutex> lock(get_solver_vulkan_mutex());
    SolverVulkanContext& vk_ctx = get_solver_vulkan_context();

    int n_features = static_cast<int>(gL.x_mean.size());
    int n_train = static_cast<int>(gL.alpha.size());

    if (n_features == 0 || n_train == 0) {
        throw std::runtime_error("GPR 参数无效");
    }

    // 确保 GPR 数据已上传
    if (!vk_state->uploaded_gpr) {
        std::size_t x_train_bytes = static_cast<std::size_t>(n_train) * static_cast<std::size_t>(n_features) * sizeof(float);
        std::size_t alpha_bytes = static_cast<std::size_t>(n_train) * sizeof(float);

        if (vk_state->gpr_X_train_bytes < x_train_bytes) {
            destroy_buffer(vk_ctx.device, vk_state->gpr_X_train);
            vk_state->gpr_X_train = create_buffer(vk_ctx.device, vk_ctx.physical_device, x_train_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->gpr_X_train_bytes = x_train_bytes;
        }
        if (vk_state->gpr_alpha_bytes < alpha_bytes) {
            destroy_buffer(vk_ctx.device, vk_state->gpr_alpha_L);
            destroy_buffer(vk_ctx.device, vk_state->gpr_alpha_a);
            destroy_buffer(vk_ctx.device, vk_state->gpr_alpha_b);
            vk_state->gpr_alpha_L = create_buffer(vk_ctx.device, vk_ctx.physical_device, alpha_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->gpr_alpha_a = create_buffer(vk_ctx.device, vk_ctx.physical_device, alpha_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->gpr_alpha_b = create_buffer(vk_ctx.device, vk_ctx.physical_device, alpha_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
            vk_state->gpr_alpha_bytes = alpha_bytes;
        }

        void* ptr = nullptr;
        vk_check(vkMapMemory(vk_ctx.device, vk_state->gpr_X_train.memory, 0, x_train_bytes, 0, &ptr), "vkMapMemory(X_train)");
        std::memcpy(ptr, gL.X_train.data(), x_train_bytes);
        vkUnmapMemory(vk_ctx.device, vk_state->gpr_X_train.memory);

        vk_check(vkMapMemory(vk_ctx.device, vk_state->gpr_alpha_L.memory, 0, alpha_bytes, 0, &ptr), "vkMapMemory(alpha_L)");
        std::memcpy(ptr, gL.alpha.data(), alpha_bytes);
        vkUnmapMemory(vk_ctx.device, vk_state->gpr_alpha_L.memory);

        vk_check(vkMapMemory(vk_ctx.device, vk_state->gpr_alpha_a.memory, 0, alpha_bytes, 0, &ptr), "vkMapMemory(alpha_a)");
        std::memcpy(ptr, ga.alpha.data(), alpha_bytes);
        vkUnmapMemory(vk_ctx.device, vk_state->gpr_alpha_a.memory);

        vk_check(vkMapMemory(vk_ctx.device, vk_state->gpr_alpha_b.memory, 0, alpha_bytes, 0, &ptr), "vkMapMemory(alpha_b)");
        std::memcpy(ptr, gb.alpha.data(), alpha_bytes);
        vkUnmapMemory(vk_ctx.device, vk_state->gpr_alpha_b.memory);

        vk_state->gpr_n_train = static_cast<std::uint32_t>(n_train);
        vk_state->gpr_n_features = static_cast<std::uint32_t>(n_features);
        vk_state->uploaded_gpr = true;
    }

    // 创建输入 X 缓冲区
    std::size_t x_bytes = static_cast<std::size_t>(n_samples) * static_cast<std::size_t>(n_features) * sizeof(float);
    VulkanBuffer x_buf = create_buffer(vk_ctx.device, vk_ctx.physical_device, x_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
    ScopedVulkanBuffer x_guard(vk_ctx.device, x_buf);

    void* ptr = nullptr;
    vk_check(vkMapMemory(vk_ctx.device, x_buf.memory, 0, x_bytes, 0, &ptr), "vkMapMemory(X)");
    std::memcpy(ptr, X.data(), x_bytes);
    vkUnmapMemory(vk_ctx.device, x_buf.memory);

    // 创建输出缓冲区
    std::size_t out_bytes = static_cast<std::size_t>(n_samples) * 3u * sizeof(float);
    VulkanBuffer out_buf = create_buffer(vk_ctx.device, vk_ctx.physical_device, out_bytes, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
    ScopedVulkanBuffer out_guard(vk_ctx.device, out_buf);

    // 更新描述符集
    VkDescriptorBufferInfo x_info{};
    x_info.buffer = x_buf.buffer;
    x_info.offset = 0;
    x_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo x_train_info{};
    x_train_info.buffer = vk_state->gpr_X_train.buffer;
    x_train_info.offset = 0;
    x_train_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo alpha_L_info{};
    alpha_L_info.buffer = vk_state->gpr_alpha_L.buffer;
    alpha_L_info.offset = 0;
    alpha_L_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo alpha_a_info{};
    alpha_a_info.buffer = vk_state->gpr_alpha_a.buffer;
    alpha_a_info.offset = 0;
    alpha_a_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo alpha_b_info{};
    alpha_b_info.buffer = vk_state->gpr_alpha_b.buffer;
    alpha_b_info.offset = 0;
    alpha_b_info.range = VK_WHOLE_SIZE;

    VkDescriptorBufferInfo out_info{};
    out_info.buffer = out_buf.buffer;
    out_info.offset = 0;
    out_info.range = VK_WHOLE_SIZE;

    VkWriteDescriptorSet writes[6] = {};

    writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[0].dstSet = vk_ctx.gpr_descriptor_set;
    writes[0].dstBinding = 0;
    writes[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[0].descriptorCount = 1;
    writes[0].pBufferInfo = &x_info;

    writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[1].dstSet = vk_ctx.gpr_descriptor_set;
    writes[1].dstBinding = 1;
    writes[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[1].descriptorCount = 1;
    writes[1].pBufferInfo = &x_train_info;

    writes[2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[2].dstSet = vk_ctx.gpr_descriptor_set;
    writes[2].dstBinding = 2;
    writes[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[2].descriptorCount = 1;
    writes[2].pBufferInfo = &alpha_L_info;

    writes[3].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[3].dstSet = vk_ctx.gpr_descriptor_set;
    writes[3].dstBinding = 3;
    writes[3].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[3].descriptorCount = 1;
    writes[3].pBufferInfo = &alpha_a_info;

    writes[4].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[4].dstSet = vk_ctx.gpr_descriptor_set;
    writes[4].dstBinding = 4;
    writes[4].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[4].descriptorCount = 1;
    writes[4].pBufferInfo = &alpha_b_info;

    writes[5].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[5].dstSet = vk_ctx.gpr_descriptor_set;
    writes[5].dstBinding = 5;
    writes[5].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[5].descriptorCount = 1;
    writes[5].pBufferInfo = &out_info;

    vkUpdateDescriptorSets(vk_ctx.device, 6, writes, 0, nullptr);

    // 分配命令缓冲区
    VkCommandBufferAllocateInfo cbai{};
    cbai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cbai.commandPool = vk_ctx.command_pool;
    cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cbai.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    vk_check(vkAllocateCommandBuffers(vk_ctx.device, &cbai, &cmd), "vkAllocateCommandBuffers");
    ScopedCommandBuffer cmd_guard(vk_ctx.device, vk_ctx.command_pool, cmd);

    // 记录命令
    VkCommandBufferBeginInfo cbbi{};
    cbbi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    cbbi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vk_check(vkBeginCommandBuffer(cmd, &cbbi), "vkBeginCommandBuffer");

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, vk_ctx.gpr_pipeline);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, vk_ctx.gpr_pipeline_layout, 0, 1, &vk_ctx.gpr_descriptor_set, 0, nullptr);

    struct PushConstants {
        std::uint32_t n_samples;
        std::uint32_t n_train;
        std::uint32_t n_features;
        std::uint32_t pad0;
        float lengthscale[4];
        float signal_var[4];
        float y_mean[4];
        float y_std[4];
    } pc;

    pc.n_samples = static_cast<std::uint32_t>(n_samples);
    pc.n_train = vk_state->gpr_n_train;
    pc.n_features = vk_state->gpr_n_features;
    pc.pad0 = 0;

    pc.lengthscale[0] = gL.lengthscale;
    pc.lengthscale[1] = ga.lengthscale;
    pc.lengthscale[2] = gb.lengthscale;
    pc.lengthscale[3] = 0.0f;

    pc.signal_var[0] = gL.signal_var;
    pc.signal_var[1] = ga.signal_var;
    pc.signal_var[2] = gb.signal_var;
    pc.signal_var[3] = 0.0f;

    pc.y_mean[0] = gL.y_mean;
    pc.y_mean[1] = ga.y_mean;
    pc.y_mean[2] = gb.y_mean;
    pc.y_mean[3] = 0.0f;

    pc.y_std[0] = gL.y_std;
    pc.y_std[1] = ga.y_std;
    pc.y_std[2] = gb.y_std;
    pc.y_std[3] = 0.0f;

    vkCmdPushConstants(cmd, vk_ctx.gpr_pipeline_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);

    std::uint32_t total_invocations = static_cast<std::uint32_t>(n_samples) * 3u;
    std::uint32_t group_count = (total_invocations + 255u) / 256u;
    vkCmdDispatch(cmd, group_count, 1, 1);

    vk_check(vkEndCommandBuffer(cmd), "vkEndCommandBuffer");

    // 提交命令
    VkSubmitInfo si{};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cmd;
    vk_check(vkQueueSubmit(vk_ctx.queue, 1, &si, VK_NULL_HANDLE), "vkQueueSubmit");
    vk_check(vkQueueWaitIdle(vk_ctx.queue), "vkQueueWaitIdle");

    // 读取结果
    std::vector<float> result(static_cast<std::size_t>(n_samples) * 3u);
    vk_check(vkMapMemory(vk_ctx.device, out_buf.memory, 0, out_bytes, 0, &ptr), "vkMapMemory(out)");
    std::memcpy(result.data(), ptr, out_bytes);
    vkUnmapMemory(vk_ctx.device, out_buf.memory);

    return result;
}

} // namespace solver
} // namespace opencolor
