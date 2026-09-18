cmake_minimum_required(VERSION 3.20)
project(qbrain_search_arguments_review LANGUAGES CXX)

# Independent executable: the original native test driver appends TestSources
# to its canonical main(), so a standalone main() must not be sent to it.
get_filename_component(QBRAIN_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
add_executable(qbrain_search_arguments_tests
  "${QBRAIN_ROOT}/.ci/search_arguments_unit.cpp"
  "${QBRAIN_ROOT}/src/qbrain/util/string_util.cpp")
target_include_directories(qbrain_search_arguments_tests PRIVATE "${QBRAIN_ROOT}/include")
target_compile_features(qbrain_search_arguments_tests PRIVATE cxx_std_20)
if(MSVC)
  target_compile_options(qbrain_search_arguments_tests PRIVATE /utf-8 /W4 /WX)
  target_compile_definitions(qbrain_search_arguments_tests PRIVATE NOMINMAX)
else()
  target_compile_options(qbrain_search_arguments_tests PRIVATE -Wall -Wextra -Werror)
endif()
enable_testing()
add_test(NAME search_arguments COMMAND qbrain_search_arguments_tests)
