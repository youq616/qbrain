# N48X adds tests without altering the frozen N48W target registration.
include("${CMAKE_SOURCE_DIR}/.ci/runtime_observation_targets.cmake")
function(qbrain_add_logical_observation_tests)
  find_package(Threads REQUIRED)
  foreach(kind logical_observation logical_observation_http)
    add_executable(qbrain_${kind}_tests "${CMAKE_SOURCE_DIR}/tests/test_${kind}.cpp")
    target_link_libraries(qbrain_${kind}_tests PRIVATE
      qbrain_search qbrain_ai qbrain_core qbrain_search qbrain_jobs qbrain_ai qbrain_util Threads::Threads)
  endforeach()
  add_executable(qbrain_logical_rerank_regression
    "${CMAKE_SOURCE_DIR}/tests/test_logical_rerank_regression.cpp"
    "${CMAKE_SOURCE_DIR}/tests/test_rerank.cpp")
  target_link_libraries(qbrain_logical_rerank_regression PRIVATE
    qbrain_search qbrain_ai qbrain_core qbrain_search qbrain_jobs qbrain_ai qbrain_util Threads::Threads)
  if(WIN32)
    target_sources(qbrain_logical_rerank_regression PRIVATE "${CMAKE_SOURCE_DIR}/tests/test_n39.cpp")
    target_link_libraries(qbrain_logical_rerank_regression PRIVATE ws2_32)
  endif()
  add_test(NAME qbrain_logical_rerank_regression COMMAND qbrain_logical_rerank_regression)
  set_tests_properties(qbrain_logical_rerank_regression PROPERTIES TIMEOUT 90)
  add_test(NAME qbrain_logical_observation_unit COMMAND qbrain_logical_observation_tests)
  set_tests_properties(qbrain_logical_observation_unit PROPERTIES TIMEOUT 90)
endfunction()
cmake_language(DEFER CALL qbrain_add_logical_observation_tests)
