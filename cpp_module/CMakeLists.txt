# 指定 CMake 的最低版本要求
cmake_minimum_required(VERSION 3.24)

# 设置策略 CMP0148，以兼容较新的 CMake 版本中对 FindPythonLibs 和 FindPythonInterp 的处理
if(POLICY CMP0148)
  cmake_policy(SET CMP0148 NEW)
endif()

# 如果未定义 CMAKE_TOOLCHAIN_FILE 且存在 vcpkg 脚本，则自动设置 vcpkg 工具链文件
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/vcpkg/scripts/buildsystems/vcpkg.cmake")
  set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_LIST_DIR}/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "")
endif()

# 定义项目名称及支持的语言
project(opencolor_cpp_module LANGUAGES C CXX)

# 设置 C++ 标准为 C++20，并要求编译器必须支持该标准
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(OPENCOLOR_BUILD_CORE "构建 OpenColor C++ 核心模块（pybind/Vulkan 等）" ON)
option(OPENCOLOR_BUILD_DEV_TOOLS "构建开发用途工具（例如注释覆盖率分析）" OFF)

# 定义 GUI 相关的源文件列表
set(_opencolor_gui_sources
  src/main.cpp
  src/vulkan_app.cpp
  src/vulkan_helpers.cpp
)

if(OPENCOLOR_BUILD_CORE)
  # 添加颜色接触搜索的可执行文件目标
  add_executable(opencolor_color_contact_search
    src/color_contact_search.cpp
  )

  # 添加 Web 探测的可执行文件目标
  add_executable(opencolor_web_probe
    src/web_probe.cpp
  )

  # 查找 shaderc 库（用于 Vulkan 着色器编译）
  find_package(unofficial-shaderc CONFIG REQUIRED)
  # 查找 Vulkan SDK
  find_package(Vulkan REQUIRED)
  find_package(Clipper2 CONFIG REQUIRED)
  find_package(manifold CONFIG REQUIRED)

  # 设置 vcpkg 安装目录的包含路径
  set(_opencolor_vcpkg_include "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/include")

  # 查找 Python 路径
  execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import sysconfig; print(sysconfig.get_paths()['include'])"
    OUTPUT_VARIABLE _python_include
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import sysconfig; import os; libdir = sysconfig.get_config_var('LIBDIR') or os.path.join(sysconfig.get_config_var('prefix'), 'libs'); print(libdir)"
    OUTPUT_VARIABLE _python_libdir
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX') or '')"
    OUTPUT_VARIABLE _python_ext_suffix
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  if(_python_ext_suffix STREQUAL "")
    set(_python_ext_suffix ".pyd")
  endif()


  # 添加新的模型模块（包含模块化接口）
  add_library(opencolor_models MODULE
    src/models/model_pybind.cpp
    src/models/model_base.cpp
    src/models/models.cpp
  )

  # 为 opencolor_models 目标设置包含目录
  target_include_directories(opencolor_models PRIVATE
    ${_opencolor_vcpkg_include}
    ${_python_include}
    src
  )

  # 为 opencolor_models 目标链接必要的库
  target_link_libraries(opencolor_models PRIVATE
    Vulkan::Vulkan
    unofficial::shaderc::shaderc
  )
  target_link_directories(opencolor_models PRIVATE ${_python_libdir})

  # 设置 opencolor_models 模块属性
  set_target_properties(opencolor_models PROPERTIES
    PREFIX ""
    SUFFIX "${_python_ext_suffix}"
  )

  # 添加 HillClimbingSolver 模块
  add_library(opencolor_solver MODULE
    src/solver/solver_pybind.cpp
    src/solver/hill_climbing_solver.cpp
    src/solver/hill_climbing_gpr.cpp
    src/solver/hill_climbing_rt_slab.cpp
    src/solver/hill_climbing_four_flux.cpp
    src/solver/color_utils.cpp
    src/solver/vulkan_buffer.cpp
    src/solver/vulkan_context.cpp
    src/solver/vulkan_shader.cpp
    src/solver/vulkan_predictors.cpp
    src/solver/icm_joint_optimizer.cpp
    src/solver/vulkan_recipe_map_shader.cpp
    src/solver/vulkan_recipe_map.cpp
  )

  # 为 opencolor_solver 目标设置包含目录
  target_include_directories(opencolor_solver PRIVATE
    ${_opencolor_vcpkg_include}
    ${_python_include}
    src
  )

  # 为 opencolor_solver 目标链接必要的库
  target_link_libraries(opencolor_solver PRIVATE
    Vulkan::Vulkan
    unofficial::shaderc::shaderc
  )
  target_link_directories(opencolor_solver PRIVATE ${_python_libdir})

  # 设置 opencolor_solver 模块属性
  set_target_properties(opencolor_solver PROPERTIES
    PREFIX ""
    SUFFIX "${_python_ext_suffix}"
  )

  add_library(opencolor_geometry MODULE
    src/geometry/geometry_pybind.cpp
    src/geometry/clipper_ops.cpp
    src/geometry/earcut_triangulation.cpp
    src/geometry/manifold_ops.cpp
    src/geometry/mesh_utils.cpp
    src/geometry/svg_loader.cpp
  )

  target_include_directories(opencolor_geometry PRIVATE
    ${_opencolor_vcpkg_include}
    ${_python_include}
    src
  )

  find_package(NanoSVG CONFIG REQUIRED)

  target_link_libraries(opencolor_geometry PRIVATE
    Clipper2::Clipper2
    manifold::manifold
    NanoSVG::nanosvg
  )

  target_link_directories(opencolor_geometry PRIVATE ${_python_libdir})

  set_target_properties(opencolor_geometry PROPERTIES
    PREFIX ""
    SUFFIX "${_python_ext_suffix}"
  )
endif()

if(OPENCOLOR_BUILD_DEV_TOOLS)
  add_subdirectory(tools/comment_coverage_ts)
endif()

