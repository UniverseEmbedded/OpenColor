cmake_minimum_required(VERSION 3.24)

project(opencolor_comment_coverage_ts LANGUAGES C CXX)

find_package(unofficial-tree-sitter CONFIG REQUIRED)

include(FetchContent)

set(FETCHCONTENT_QUIET OFF)

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

function(opencolor_add_tree_sitter_grammar_from_src_dir target src_dir)
  set(_parser "${src_dir}/parser.c")
  if(NOT EXISTS "${_parser}")
    message(FATAL_ERROR "未找到 grammar 生成的 parser.c: ${_parser}")
  endif()

  add_library(${target} STATIC "${_parser}")
  target_include_directories(${target} PUBLIC "${src_dir}")
  target_link_libraries(${target} PUBLIC unofficial::tree-sitter::tree-sitter)

  if(EXISTS "${src_dir}/scanner.c")
    target_sources(${target} PRIVATE "${src_dir}/scanner.c")
  endif()
  if(EXISTS "${src_dir}/scanner.cc")
    target_sources(${target} PRIVATE "${src_dir}/scanner.cc")
    set_source_files_properties("${src_dir}/scanner.cc" PROPERTIES LANGUAGE CXX)
  endif()
  if(EXISTS "${src_dir}/scanner.cpp")
    target_sources(${target} PRIVATE "${src_dir}/scanner.cpp")
    set_source_files_properties("${src_dir}/scanner.cpp" PROPERTIES LANGUAGE CXX)
  endif()

  target_compile_features(${target} PUBLIC cxx_std_20)
endfunction()

set(_ts_tag_c "v0.20.6")
set(_ts_tag_cpp "v0.20.5")
set(_ts_tag_python "v0.20.4")
set(_ts_tag_javascript "v0.20.4")
set(_ts_tag_typescript "v0.20.6")
set(_ts_tag_java "v0.20.2")
set(_ts_tag_c_sharp "v0.20.0")
set(_ts_tag_go "v0.20.0")
set(_ts_tag_rust "v0.20.4")
set(_ts_tag_bash "v0.20.5")
set(_ts_tag_json "v0.20.2")
set(_ts_tag_toml "v0.5.1")

opencolor_add_tree_sitter_grammar(cc_ts_lang_c "https://github.com/tree-sitter/tree-sitter-c.git" "${_ts_tag_c}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_cpp "https://github.com/tree-sitter/tree-sitter-cpp.git" "${_ts_tag_cpp}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_python "https://github.com/tree-sitter/tree-sitter-python.git" "${_ts_tag_python}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_javascript "https://github.com/tree-sitter/tree-sitter-javascript.git" "${_ts_tag_javascript}")

FetchContent_Declare(
  ts_typescript_src
  GIT_REPOSITORY "https://github.com/tree-sitter/tree-sitter-typescript.git"
  GIT_TAG "${_ts_tag_typescript}"
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(ts_typescript_src)
opencolor_add_tree_sitter_grammar_from_src_dir(cc_ts_lang_typescript "${ts_typescript_src_SOURCE_DIR}/typescript/src")
opencolor_add_tree_sitter_grammar_from_src_dir(cc_ts_lang_tsx "${ts_typescript_src_SOURCE_DIR}/tsx/src")

opencolor_add_tree_sitter_grammar(cc_ts_lang_java "https://github.com/tree-sitter/tree-sitter-java.git" "${_ts_tag_java}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_c_sharp "https://github.com/tree-sitter/tree-sitter-c-sharp.git" "${_ts_tag_c_sharp}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_go "https://github.com/tree-sitter/tree-sitter-go.git" "${_ts_tag_go}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_rust "https://github.com/tree-sitter/tree-sitter-rust.git" "${_ts_tag_rust}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_bash "https://github.com/tree-sitter/tree-sitter-bash.git" "${_ts_tag_bash}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_json "https://github.com/tree-sitter/tree-sitter-json.git" "${_ts_tag_json}")
opencolor_add_tree_sitter_grammar(cc_ts_lang_toml "https://github.com/tree-sitter/tree-sitter-toml.git" "${_ts_tag_toml}")

add_executable(opencolor_comment_coverage_ts
  src/main.cpp
)

target_compile_features(opencolor_comment_coverage_ts PRIVATE cxx_std_20)

target_link_libraries(opencolor_comment_coverage_ts PRIVATE
  unofficial::tree-sitter::tree-sitter
  cc_ts_lang_c
  cc_ts_lang_cpp
  cc_ts_lang_python
  cc_ts_lang_javascript
  cc_ts_lang_typescript
  cc_ts_lang_tsx
  cc_ts_lang_java
  cc_ts_lang_c_sharp
  cc_ts_lang_go
  cc_ts_lang_rust
  cc_ts_lang_bash
  cc_ts_lang_json
  cc_ts_lang_toml
)
