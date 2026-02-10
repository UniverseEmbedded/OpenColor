#include <chrono>
#include <iostream>
#include <string>
#include <vector>

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
 * Web 探测程序入口
 * 解析命令行参数，输出 JSON 格式的连接确认信息
 */
int main(int argc, char** argv)
{
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
