/**
 * @file color_utils.h
 * @brief 颜色工具函数
 *
 * 提供 RGB 与 Lab 颜色空间转换以及 Sigmoid 激活函数
 */

#pragma once

namespace opencolor {
namespace solver {

/**
 * @brief 将 RGB (0-1范围) 转换为 Lab 颜色空间
 * @param rgb 输入 RGB 数组 [3]
 * @param lab 输出 Lab 数组 [3]
 */
void rgb01_to_lab(const float* rgb, float* lab);

/**
 * @brief 将 Lab 颜色空间转换为 RGB (0-1范围)
 * @param lab 输入 Lab 数组 [3]
 * @param rgb 输出 RGB 数组 [3]
 */
void lab_to_rgb01(const float* lab, float* rgb);

/**
 * @brief Sigmoid 激活函数
 * @param x 输入值
 * @return Sigmoid 输出值
 */
float sigmoid(float x);

} // namespace solver
} // namespace opencolor
