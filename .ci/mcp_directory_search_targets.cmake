# Additive overlay: inherited build files and tests remain byte-identical.
function(qbrain_add_mcp_directory_search_tests)
  add_executable(qbrain_mcp_directory_search_tests "${CMAKE_SOURCE_DIR}/tests/test_mcp_directory_search.cpp")
  target_link_libraries(qbrain_mcp_directory_search_tests PRIVATE qbrain_mcp qbrain_ops qbrain_search qbrain_core qbrain_ai)
  add_test(NAME qbrain_mcp_directory_search_unit COMMAND qbrain_mcp_directory_search_tests)
endfunction()
cmake_language(DEFER CALL qbrain_add_mcp_directory_search_tests)
include("${CMAKE_SOURCE_DIR}/.ci/directory_search_targets.cmake")
