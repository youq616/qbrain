# N48T opt-in test registration; ordinary product target inventory is unchanged.
function(qbrain_add_context_invalidation_tests)
  add_executable(qbrain_context_invalidation_tests "${CMAKE_SOURCE_DIR}/tests/test_context_invalidation.cpp")
  target_link_libraries(qbrain_context_invalidation_tests PRIVATE qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
  add_test(NAME qbrain_context_invalidation_unit COMMAND qbrain_context_invalidation_tests)
endfunction()
cmake_language(DEFER CALL qbrain_add_context_invalidation_tests)
