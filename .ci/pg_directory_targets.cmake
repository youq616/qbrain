# N48U read-only SQL target; no change to PR62 targets or root CMake inventory.
function(qbrain_pg_directory_targets)
  add_executable(qbrain_pg_directory_predicate_tests "${CMAKE_SOURCE_DIR}/tests/test_pg_directory_predicate.cpp")
  target_link_libraries(qbrain_pg_directory_predicate_tests PRIVATE qbrain_storage qbrain_util)
endfunction()
cmake_language(DEFER CALL qbrain_pg_directory_targets)
