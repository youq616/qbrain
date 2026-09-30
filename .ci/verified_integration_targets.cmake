# N49A: register the exact accepted test modules once on one combined product.
include("${CMAKE_SOURCE_DIR}/.ci/context_invalidation_targets.cmake")
include("${CMAKE_SOURCE_DIR}/.ci/query_embedding_targets.cmake")
include("${CMAKE_SOURCE_DIR}/.ci/logical_observation_targets.cmake")
include("${CMAKE_SOURCE_DIR}/.ci/pg_hook_targets.cmake")
function(qbrain_add_verified_integration_tests)
  find_package(Threads REQUIRED)
  add_executable(qbrain_verified_integration_tests "${CMAKE_SOURCE_DIR}/tests/test_verified_integration.cpp")
  target_link_libraries(qbrain_verified_integration_tests PRIVATE
    qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai Threads::Threads)
  add_test(NAME qbrain_verified_integration_unit COMMAND qbrain_verified_integration_tests)
  set_tests_properties(qbrain_verified_integration_unit PROPERTIES TIMEOUT 90)
endfunction()
cmake_language(DEFER CALL qbrain_add_verified_integration_tests)
