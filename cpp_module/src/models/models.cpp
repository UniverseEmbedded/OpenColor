#include "models.h"

namespace opencolor {
namespace models {

void initialize_models() {
    // 模型通过REGISTER_COLOR_MODEL宏自动注册
    // 此函数可用于执行额外的初始化操作
}

const char* get_models_version() {
    return "1.0.0";
}

} // namespace models
} // namespace opencolor
