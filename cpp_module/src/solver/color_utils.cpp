#include "color_utils.h"

#include <algorithm>
#include <cmath>

namespace opencolor {
namespace solver {

/**
 * Sigmoid激活函数
 *
 * 计算输入值的sigmoid，将值限制在[-20, 20]范围内以避免数值溢出
 *
 * @param x 输入值
 * @return sigmoid(x) = 1 / (1 + exp(-x))
 */
float sigmoid(float x) {
    x = std::max(-20.0f, std::min(20.0f, x));
    return 1.0f / (1.0f + std::exp(-x));
}

/**
 * 将RGB[0,1]颜色空间转换为CIE Lab颜色空间
 *
 * 转换步骤：
 * 1. 应用Gamma校正将sRGB转换为线性RGB
 * 2. 将线性RGB转换为XYZ颜色空间
 * 3. 将XYZ转换为CIE Lab颜色空间
 *
 * @param rgb 输入RGB数组，范围[0,1]，长度为3
 * @param lab 输出Lab数组，长度为3（L: [0,100], a,b: [-128,127]）
 */
void rgb01_to_lab(const float* rgb, float* lab) {
    // Gamma校正：将sRGB转换为线性RGB
    auto gamma_correct = [](float c) {
        return (c > 0.04045f) ? std::pow((c + 0.055f) / 1.055f, 2.4f) : c / 12.92f;
    };

    float r = gamma_correct(rgb[0]);
    float g = gamma_correct(rgb[1]);
    float b = gamma_correct(rgb[2]);

    // RGB到XYZ的转换矩阵（D65白点）
    float x = r * 0.4124564f + g * 0.3575761f + b * 0.1804375f;
    float y = r * 0.2126729f + g * 0.7151522f + b * 0.0721750f;
    float z = r * 0.0193339f + g * 0.1191920f + b * 0.9503041f;

    // CIE Lab转换中的f函数
    auto f = [](float t) {
        const float delta = 6.0f / 29.0f;
        if (t > delta * delta * delta) {
            return std::cbrt(t);
        } else {
            return t / (3.0f * delta * delta) + 4.0f / 29.0f;
        }
    };

    // 归一化到D65白点
    float xn = x / 0.95047f;
    float yn = y / 1.00000f;
    float zn = z / 1.08883f;

    float fx = f(xn);
    float fy = f(yn);
    float fz = f(zn);

    // 计算Lab值
    lab[0] = 116.0f * fy - 16.0f;      // L: 明度 [0, 100]
    lab[1] = 500.0f * (fx - fy);       // a: 绿-红轴 [-128, 127]
    lab[2] = 200.0f * (fy - fz);       // b: 蓝-黄轴 [-128, 127]
}

/**
 * 将CIE Lab颜色空间转换为RGB[0,1]颜色空间
 *
 * 转换步骤：
 * 1. 将Lab转换为XYZ颜色空间
 * 2. 将XYZ转换为线性RGB
 * 3. 应用逆Gamma校正将线性RGB转换为sRGB
 *
 * @param lab 输入Lab数组，长度为3
 * @param rgb 输出RGB数组，范围[0,1]，长度为3
 */
void lab_to_rgb01(const float* lab, float* rgb) {
    // Lab到XYZ的转换
    float fy = (lab[0] + 16.0f) / 116.0f;
    float fx = lab[1] / 500.0f + fy;
    float fz = fy - lab[2] / 200.0f;

    // CIE Lab转换中的f函数逆函数
    auto f_inv = [](float t) {
        const float delta = 6.0f / 29.0f;
        if (t > delta) {
            return t * t * t;
        } else {
            return 3.0f * delta * delta * (t - 4.0f / 29.0f);
        }
    };

    float xn = f_inv(fx);
    float yn = f_inv(fy);
    float zn = f_inv(fz);

    // 反归一化
    float x = xn * 0.95047f;
    float y = yn * 1.00000f;
    float z = zn * 1.08883f;

    // XYZ到RGB的转换矩阵（D65白点）
    float r = x *  3.2404542f + y * -1.5371385f + z * -0.4985314f;
    float g = x * -0.9692660f + y *  1.8760108f + z *  0.0415560f;
    float b = x *  0.0556434f + y * -0.2040259f + z *  1.0572252f;

    // 逆Gamma校正：将线性RGB转换为sRGB
    auto gamma_correct_inv = [](float c) {
        return (c > 0.0031308f) ? 1.055f * std::pow(c, 1.0f / 2.4f) - 0.055f : 12.92f * c;
    };

    // 裁剪到[0,1]范围
    rgb[0] = std::max(0.0f, std::min(1.0f, gamma_correct_inv(r)));
    rgb[1] = std::max(0.0f, std::min(1.0f, gamma_correct_inv(g)));
    rgb[2] = std::max(0.0f, std::min(1.0f, gamma_correct_inv(b)));
}

} // namespace solver
} // namespace opencolor
