# Opt-in native test target without changing the default product target inventory.
# cmake -S . -B build/hook -DCMAKE_PROJECT_qbrain_INCLUDE=<absolute path to this file>
function(qbrain_add_pg_hook_tests)
  add_executable(qbrain_pg_hook_tests "${CMAKE_SOURCE_DIR}/tests/test_pg_hooks.cpp")
  target_link_libraries(qbrain_pg_hook_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
  add_test(NAME qbrain_pg_hook_sqlite_unit COMMAND qbrain_pg_hook_tests --sqlite-only)
endfunction()
cmake_language(DEFER CALL qbrain_add_pg_hook_tests)
