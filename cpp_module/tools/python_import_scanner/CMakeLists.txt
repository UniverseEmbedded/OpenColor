cmake_minimum_required(VERSION 3.24)

project(opencolor_python_import_scanner LANGUAGES C CXX)

find_package(unofficial-tree-sitter CONFIG REQUIRED)

include(FetchContent)

set(FETCHCONTENT_QUIET OFF)

# 添加 tree-sitter grammar 的函数
function(opencolor_add_tree_sitter_grammar target repo tag)
  FetchContent_Declare(
    ${target}_src
    GIT_REPOSITORY ${repo}
    GIT_TAG ${tag}
    GIT_SHALLOW TRUE
  )
  FetchContent_MakeAvailable(${target}_src)

  set(_src_dir "${${target}_src_SOURCE_DIR}/src")
  set(_parser "${_src_dir}/parser.c")
  if(NOT EXISTS "${_parser}")
    message(FATAL_ERROR "未找到 grammar 生成的 parser.c: ${_parser}")
  endif()

  add_library(${target} STATIC "${_parser}")
  target_include_directories(${target} PUBLIC "${${target}_src_SOURCE_DIR}/src")
  target_link_libraries(${target} PUBLIC unofficial::tree-sitter::tree-sitter)

  if(EXISTS "${_src_dir}/scanner.c")
    target_sources(${target} PRIVATE "${_src_dir}/scanner.c")
  endif()

  if(EXISTS "${_src_dir}/scanner.cc")
    target_sources(${target} PRIVATE "${_src_dir}/scanner.cc")
    set_source_files_properties("${_src_dir}/scanner.cc" PROPERTIES LANGUAGE CXX)
  endif()

  if(EXISTS "${_src_dir}/scanner.cpp")
    target_sources(${target} PRIVATE "${_src_dir}/scanner.cpp")
    set_source_files_properties("${_src_dir}/scanner.cpp" PROPERTIES LANGUAGE CXX)
  endif()

  target_compile_features(${target} PUBLIC cxx_std_20)
endfunction()

# 添加 Python grammar
set(_ts_tag_python "v0.20.4")
opencolor_add_tree_sitter_grammar(pis_ts_lang_python "https://github.com/tree-sitter/tree-sitter-python.git" "${_ts_tag_python}")

# 创建可执行文件
add_executable(opencolor_python_import_scanner
  src/main.cpp
)

target_compile_features(opencolor_python_import_scanner PRIVATE cxx_std_20)

# 链接库
target_link_libraries(opencolor_python_import_scanner PRIVATE
  unofficial::tree-sitter::tree-sitter
  pis_ts_lang_python
)

# Windows 特定设置
if(WIN32)
  target_compile_definitions(opencolor_python_import_scanner PRIVATE
    NOMINMAX
    WIN32_LEAN_AND_MEAN
  )
endif()
