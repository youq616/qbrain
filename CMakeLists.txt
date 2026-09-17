cmake_minimum_required(VERSION 3.24)
# N37 D2: version single source of truth (0.1.0 -> 2.0.0 for the Phase-2
# release). include/qbrain/version.hpp constants must stay in sync (asserted
# by the n37_packaging unit and the N37 hard audit).
project(qbrain VERSION 2.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
  add_compile_options(/utf-8 /W3 /EHsc)
  add_compile_definitions(UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
  # Allow builds without full Windows SDK rc.exe/mt.exe (manifest tooling).
  add_link_options(/MANIFEST:NO)
  set(CMAKE_RC_COMPILER "")
  set(CMAKE_MT "")
endif()

set(SQLITE_DIR ${CMAKE_SOURCE_DIR}/third_party/sqlite/sqlite-amalgamation-3460100)
set(NLOHMANN_DIR ${CMAKE_SOURCE_DIR}/third_party)

# ---------------------------------------------------------------------------
# N38: libpq (PostgreSQL) discovery + QBRAIN_WITH_PG switch.
# Order: QBRAIN_PG_ROOT cache var -> $QBRAIN_PG_ROOT env -> well-known roots
# D:/PostgreSQL and C:/Program Files/PostgreSQL, highest numeric version
# directory that carries include/libpq-fe.h + lib/libpq.lib wins (documented
# highest-version rule, plan P2-1). Not found -> the option auto-degrades to
# OFF with a status message; pg_backend.cpp still compiles (its libpq-free
# half) and the SQLite path is never affected.
# ---------------------------------------------------------------------------
option(QBRAIN_WITH_PG "Build the libpq PostgreSQL storage backend (auto-disabled when libpq is not found)" ON)

function(qbrain_pg_discover out_root)
  foreach(_explicit "${QBRAIN_PG_ROOT}" "$ENV{QBRAIN_PG_ROOT}")
    if(_explicit AND EXISTS "${_explicit}/include/libpq-fe.h" AND EXISTS "${_explicit}/lib/libpq.lib")
      set(${out_root} "${_explicit}" PARENT_SCOPE)
      return()
    endif()
  endforeach()
  set(_best "")
  set(_best_ver -1)
  foreach(_base "D:/PostgreSQL" "C:/Program Files/PostgreSQL")
    if(NOT EXISTS "${_base}")
      continue()
    endif()
    file(GLOB _dirs RELATIVE "${_base}" "${_base}/*")
    foreach(_d ${_dirs})
      if(NOT IS_DIRECTORY "${_base}/${_d}")
        continue()
      endif()
      string(REGEX MATCH "^([0-9]+)" _ver "${_d}")
      if(NOT _ver)
        continue()
      endif()
      if(NOT _ver GREATER _best_ver)
        continue()
      endif()
      if(EXISTS "${_base}/${_d}/include/libpq-fe.h" AND EXISTS "${_base}/${_d}/lib/libpq.lib")
        set(_best "${_base}/${_d}")
        set(_best_ver "${_ver}")
      endif()
    endforeach()
  endforeach()
  set(${out_root} "${_best}" PARENT_SCOPE)
endfunction()

qbrain_pg_discover(QBRAIN_PG_DISCOVERED)
set(QBRAIN_PG_ENABLED OFF)
if(QBRAIN_WITH_PG AND QBRAIN_PG_DISCOVERED)
  set(QBRAIN_PG_ENABLED ON)
  message(STATUS "N38: libpq found at ${QBRAIN_PG_DISCOVERED} -- QBRAIN_WITH_PG ON")
elseif(QBRAIN_WITH_PG)
  message(STATUS "N38: libpq not found (QBRAIN_PG_ROOT / D:/PostgreSQL/<max> / C:/Program Files/PostgreSQL/<max>) -- QBRAIN_WITH_PG auto-OFF; SQLite path unaffected")
endif()

add_library(sqlite3 STATIC ${SQLITE_DIR}/sqlite3.c)
target_include_directories(sqlite3 PUBLIC ${SQLITE_DIR})
target_compile_definitions(sqlite3 PUBLIC
  SQLITE_ENABLE_FTS5
  SQLITE_THREADSAFE=1
  SQLITE_DEFAULT_WAL_SYNCHRONOUS=1
  SQLITE_OMIT_LOAD_EXTENSION
)
if(MSVC)
  target_compile_options(sqlite3 PRIVATE /wd4996)
endif()

function(qbrain_lib name)
  add_library(qbrain_${name} STATIC ${ARGN})
  target_include_directories(qbrain_${name}
    PUBLIC ${CMAKE_SOURCE_DIR}/include
    PUBLIC ${NLOHMANN_DIR}
  )
  target_link_libraries(qbrain_${name} PUBLIC sqlite3)
endfunction()

qbrain_lib(util
  src/qbrain/util/paths.cpp
  src/qbrain/util/hash.cpp
  src/qbrain/util/log.cpp
  src/qbrain/util/string_util.cpp
  src/qbrain/util/time_util.cpp
)

qbrain_lib(storage
  src/qbrain/storage/database.cpp
  src/qbrain/storage/migrate.cpp
  src/qbrain/storage/pg_backend.cpp
)
target_link_libraries(qbrain_storage PUBLIC qbrain_util)
if(QBRAIN_PG_ENABLED)
  # N38: libpq include dir + import lib + the QBRAIN_WITH_PG compile switch
  # propagate to every consumer of qbrain_storage (tests, CLI, harnesses).
  target_include_directories(qbrain_storage PUBLIC "${QBRAIN_PG_DISCOVERED}/include")
  target_link_libraries(qbrain_storage PUBLIC "${QBRAIN_PG_DISCOVERED}/lib/libpq.lib")
  target_compile_definitions(qbrain_storage PUBLIC QBRAIN_WITH_PG=1)
  if(MSVC)
    # Delay-load keeps libpq.dll off the loader path until PG is actually
    # used: executables start (and the canonical suite stays green) on
    # machines where the PostgreSQL bin dir is not on PATH. Consumers that
    # set QBRAIN_PG_DSN must have the PG bin dir on PATH (or run via
    # pg_env.bat) for the DLL's dependency closure.
    target_link_options(qbrain_storage PUBLIC "/DELAYLOAD:libpq.dll")
    target_link_libraries(qbrain_storage PUBLIC delayimp)
  endif()
endif()

qbrain_lib(core
  src/qbrain/core/types.cpp
  src/qbrain/core/brain.cpp
)
target_link_libraries(qbrain_core PUBLIC qbrain_storage qbrain_util)

qbrain_lib(schema
  src/qbrain/schema/packs.cpp
  src/qbrain/schema/lint.cpp
)
target_link_libraries(qbrain_schema PUBLIC qbrain_core qbrain_util)

qbrain_lib(graph
  src/qbrain/graph/extract.cpp
  src/qbrain/graph/traverse.cpp
  src/qbrain/graph/analytics.cpp
)
target_link_libraries(qbrain_graph PUBLIC qbrain_core qbrain_util)

qbrain_lib(codeintel
  src/qbrain/codeintel/scan.cpp
  src/qbrain/codeintel/astlite.cpp
)
target_link_libraries(qbrain_codeintel PUBLIC qbrain_core qbrain_util)

qbrain_lib(search
  src/qbrain/search/vector.cpp
  src/qbrain/search/rrf.cpp
  src/qbrain/search/hybrid.cpp
  src/qbrain/search/rerank.cpp
)
target_link_libraries(qbrain_search PUBLIC qbrain_core qbrain_util qbrain_ai)

qbrain_lib(jobs
  src/qbrain/jobs/minions.cpp
  src/qbrain/jobs/embedding_queue.cpp
)
target_link_libraries(qbrain_jobs PUBLIC qbrain_core qbrain_ai qbrain_util)

qbrain_lib(cycle
  src/qbrain/cycle/dream.cpp
)
target_link_libraries(qbrain_cycle PUBLIC qbrain_core qbrain_jobs qbrain_util)

qbrain_lib(ingest
  src/qbrain/ingest/chunker.cpp
  src/qbrain/ingest/markdown.cpp
  src/qbrain/ingest/import.cpp
)
target_link_libraries(qbrain_ingest PUBLIC qbrain_core qbrain_graph qbrain_util)

qbrain_lib(ai
  src/qbrain/ai/http_client.cpp
  src/qbrain/ai/embed.cpp
  src/qbrain/ai/chat.cpp
)
target_link_libraries(qbrain_ai PUBLIC qbrain_util)
if(WIN32)
  target_link_libraries(qbrain_ai PUBLIC winhttp)
endif()

qbrain_lib(service
  src/qbrain/service/inbox_watch.cpp
  src/qbrain/service/live_sync.cpp
)
target_link_libraries(qbrain_service PUBLIC qbrain_core qbrain_ingest qbrain_util)

qbrain_lib(files
  src/qbrain/files/store.cpp
  src/qbrain/files/image_meta.cpp
)

qbrain_lib(memory src/qbrain/memory/fact_store.cpp src/qbrain/memory/session_memory.cpp src/qbrain/integration/hook.cpp src/qbrain/integration/diagnostics.cpp src/qbrain/context/context.cpp)
target_link_libraries(qbrain_memory PUBLIC qbrain_core qbrain_ai qbrain_util)

qbrain_lib(ops
  src/qbrain/ops/memory_ops.cpp
  src/qbrain/ops/context_ops.cpp
  src/qbrain/ops/registry.cpp
  src/qbrain/ops/handlers.cpp
)
target_link_libraries(qbrain_ops PUBLIC qbrain_memory
  qbrain_core qbrain_schema qbrain_search qbrain_graph qbrain_codeintel qbrain_ingest
  qbrain_ai qbrain_jobs qbrain_cycle
  qbrain_service qbrain_files qbrain_util
)

qbrain_lib(mcp
  src/qbrain/mcp/jsonrpc.cpp
  src/qbrain/mcp/server.cpp
  src/qbrain/mcp/http_server.cpp
  src/qbrain/mcp/auth.cpp
)
target_link_libraries(qbrain_mcp PUBLIC qbrain_ops qbrain_core qbrain_util)
if(WIN32)
  target_link_libraries(qbrain_mcp PUBLIC ws2_32)
endif()

qbrain_lib(cli
  src/qbrain/cli/app.cpp
  src/qbrain/cli/commands.cpp
)
target_link_libraries(qbrain_cli PUBLIC qbrain_mcp qbrain_service qbrain_ops qbrain_core qbrain_util)

add_executable(qbrain src/qbrain/main.cpp)
target_link_libraries(qbrain PRIVATE qbrain_cli qbrain_mcp qbrain_ops qbrain_core qbrain_util)
if(WIN32)
  target_link_libraries(qbrain PRIVATE bcrypt)
endif()

enable_testing()
add_executable(qbrain_tests
  tests/test_main.cpp
  tests/test_n43.cpp
  tests/test_n45.cpp
  tests/test_n46b.cpp
  tests/test_n46c.cpp
  tests/test_n46d.cpp
  tests/test_n47a.cpp
  tests/test_n47b.cpp
  tests/test_n47c.cpp
  tests/test_n47d.cpp
  tests/test_n47e.cpp
  tests/test_n47f.cpp
  tests/test_n47g.cpp
  tests/test_n47h.cpp
  tests/test_n47i.cpp
  tests/test_n47j.cpp
  tests/test_n47k.cpp
  tests/test_n47l.cpp
  tests/test_n46f.cpp
  tests/test_rrf.cpp
  tests/n42/test_foundation.cpp
  tests/test_vector.cpp
  tests/test_chunker.cpp
  tests/test_extract.cpp
  tests/test_storage.cpp
  tests/test_mcp.cpp
  tests/test_rerank.cpp
  tests/test_minions.cpp
  tests/test_migration_v6.cpp
  tests/test_n12_dream.cpp
  tests/test_live_sync.cpp
  tests/test_n13.cpp
  tests/test_codeintel.cpp
  tests/test_analytics.cpp
  tests/test_n19.cpp
  tests/test_n20.cpp
  tests/test_n22.cpp
  tests/test_n23.cpp
  tests/test_n20_23.cpp
  tests/test_n24_25.cpp
  tests/test_n26_27.cpp
  tests/test_wave4.cpp
  tests/test_wave5.cpp
  tests/test_doctor.cpp
  tests/test_n14.cpp
  tests/test_n15.cpp
  tests/test_n16.cpp
  tests/test_n17.cpp
  tests/test_n18.cpp
  tests/test_n30.cpp
  tests/test_n31.cpp
  tests/test_n32.cpp
  tests/test_n34.cpp
  tests/test_n33.cpp
  tests/test_n35.cpp
  tests/test_n36.cpp
  tests/test_n37.cpp
  tests/test_n38.cpp
  tests/test_n39.cpp
)
target_link_libraries(qbrain_tests PRIVATE
  qbrain_cli qbrain_mcp qbrain_ops qbrain_schema qbrain_search qbrain_jobs qbrain_cycle qbrain_graph qbrain_codeintel qbrain_ingest qbrain_ai
  qbrain_storage qbrain_core qbrain_util
)
if(WIN32)
  target_link_libraries(qbrain_tests PRIVATE winhttp)
endif()
if(WIN32)
  target_link_libraries(qbrain_tests PRIVATE bcrypt)
endif()
add_test(NAME qbrain_unit COMMAND qbrain_tests)

install(TARGETS qbrain RUNTIME DESTINATION bin)

# Portable focused target uses the same production implementations as MSVC/CLI.
add_executable(qbrain_memory_tests tests/test_n43.cpp)
target_compile_definitions(qbrain_memory_tests PRIVATE QBRAIN_MEMORY_STANDALONE=1)
target_link_libraries(qbrain_memory_tests PRIVATE qbrain_ops qbrain_memory)
add_test(NAME qbrain_memory_unit COMMAND qbrain_memory_tests)

add_executable(qbrain_context_tests tests/test_n45.cpp)
target_compile_definitions(qbrain_context_tests PRIVATE QBRAIN_CONTEXT_STANDALONE=1)
target_link_libraries(qbrain_context_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory)
add_test(NAME qbrain_context_unit COMMAND qbrain_context_tests)

# Native HTTP loopback fixtures exercise the production WinHTTP implementation.
add_executable(qbrain_http_tests tests/test_n46b.cpp)
target_compile_definitions(qbrain_http_tests PRIVATE QBRAIN_HTTP_STANDALONE=1)
target_link_libraries(qbrain_http_tests PRIVATE qbrain_ai)
add_test(NAME qbrain_http_input_unit COMMAND qbrain_http_tests)
add_executable(qbrain_http_probe tests/http_probe.cpp)
target_link_libraries(qbrain_http_probe PRIVATE qbrain_ai qbrain_core qbrain_search qbrain_jobs qbrain_ai)

# N46C exact-selector, SQLite differential tests and synthetic benchmark.
add_executable(qbrain_retrieval_tests tests/test_n46c.cpp)
target_compile_definitions(qbrain_retrieval_tests PRIVATE QBRAIN_RETRIEVAL_STANDALONE=1)
target_link_libraries(qbrain_retrieval_tests PRIVATE qbrain_search qbrain_core qbrain_jobs qbrain_ai)
add_test(NAME qbrain_retrieval_unit COMMAND qbrain_retrieval_tests)

# N46D: shared embedding contract and exact model/dimension selection.
add_executable(qbrain_embedding_tests tests/test_n46d.cpp)
target_compile_definitions(qbrain_embedding_tests PRIVATE QBRAIN_EMBEDDING_STANDALONE=1)
target_link_libraries(qbrain_embedding_tests PRIVATE qbrain_search qbrain_core qbrain_jobs qbrain_ai)
add_test(NAME qbrain_embedding_unit COMMAND qbrain_embedding_tests)

# Production queues/storage/parser with deterministic, no-network HTTP interleaving.
add_executable(qbrain_embedding_queue_tests tests/test_embedding_queue.cpp)
target_link_libraries(qbrain_embedding_queue_tests PRIVATE qbrain_jobs qbrain_core qbrain_search qbrain_ai)
add_test(NAME qbrain_embedding_queue_unit COMMAND qbrain_embedding_queue_tests)

# N46F: CJK page-search supplementation and unchanged literal memory reads.
add_executable(qbrain_cjk_tests tests/test_n46f.cpp)
target_compile_definitions(qbrain_cjk_tests PRIVATE QBRAIN_CJK_STANDALONE=1)
target_link_libraries(qbrain_cjk_tests PRIVATE qbrain_memory qbrain_search qbrain_core qbrain_jobs qbrain_ai)
add_test(NAME qbrain_cjk_unit COMMAND qbrain_cjk_tests)

# N47A production evidence-backed facts; no provider or alternate storage implementation.
add_executable(qbrain_fact_tests tests/test_n47a.cpp)
target_compile_definitions(qbrain_fact_tests PRIVATE QBRAIN_FACT_STANDALONE=1)
target_link_libraries(qbrain_fact_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_fact_unit COMMAND qbrain_fact_tests)

# N47B: production paired conflict inspection, no provider or schema changes.
add_executable(qbrain_conflict_tests tests/test_n47b.cpp)
target_compile_definitions(qbrain_conflict_tests PRIVATE QBRAIN_CONFLICT_STANDALONE=1)
target_link_libraries(qbrain_conflict_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_conflict_unit COMMAND qbrain_conflict_tests)

# N47C shares the same production dependency closure as fact/conflict tests.
add_executable(qbrain_recall_tests tests/test_n47c.cpp)
target_compile_definitions(qbrain_recall_tests PRIVATE QBRAIN_RECALL_STANDALONE=1)
target_link_libraries(qbrain_recall_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_recall_unit COMMAND qbrain_recall_tests)

# N47D uses the actual Hook composer and complete evidence retrieval code.
add_executable(qbrain_hook_fact_tests tests/test_n47d.cpp)
target_compile_definitions(qbrain_hook_fact_tests PRIVATE QBRAIN_HOOK_FACT_STANDALONE=1)
target_link_libraries(qbrain_hook_fact_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_hook_fact_unit COMMAND qbrain_hook_fact_tests)

# N47E uses the real event/fact/Hook implementation.
add_executable(qbrain_promotion_tests tests/test_n47e.cpp)
target_compile_definitions(qbrain_promotion_tests PRIVATE QBRAIN_PROMOTION_STANDALONE=1)
target_link_libraries(qbrain_promotion_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_promotion_unit COMMAND qbrain_promotion_tests)

add_executable(qbrain_lifecycle_tests tests/test_n47f.cpp)
target_compile_definitions(qbrain_lifecycle_tests PRIVATE QBRAIN_LIFECYCLE_STANDALONE=1)
target_link_libraries(qbrain_lifecycle_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_lifecycle_unit COMMAND qbrain_lifecycle_tests)

# N47G: explicit atomic lifecycle batches and read-only preview.
add_executable(qbrain_lifecycle_batch_tests tests/test_n47g.cpp)
target_compile_definitions(qbrain_lifecycle_batch_tests PRIVATE QBRAIN_BATCH_STANDALONE=1)
target_link_libraries(qbrain_lifecycle_batch_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_lifecycle_batch_unit COMMAND qbrain_lifecycle_batch_tests)

# N47H: bounded metadata-only lifecycle discovery and seek continuation.
add_executable(qbrain_lifecycle_candidate_tests tests/test_n47h.cpp)
target_compile_definitions(qbrain_lifecycle_candidate_tests PRIVATE QBRAIN_CANDIDATE_STANDALONE=1)
target_link_libraries(qbrain_lifecycle_candidate_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_lifecycle_candidate_unit COMMAND qbrain_lifecycle_candidate_tests)

# N47I: unambiguous bounded raw JSON at public mutation/transport boundaries.
add_executable(qbrain_strict_json_tests tests/test_n47i.cpp)
target_compile_definitions(qbrain_strict_json_tests PRIVATE QBRAIN_STRICT_JSON_STANDALONE=1)
target_link_libraries(qbrain_strict_json_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_strict_json_unit COMMAND qbrain_strict_json_tests)

# N47J metadata projection is header-only; filesystem behavior is tested with the real Hook process.
add_executable(qbrain_hook_trace_tests tests/test_n47j.cpp)
target_compile_definitions(qbrain_hook_trace_tests PRIVATE QBRAIN_HOOK_TRACE_STANDALONE=1)
target_link_libraries(qbrain_hook_trace_tests PRIVATE qbrain_util)
add_test(NAME qbrain_hook_trace_unit COMMAND qbrain_hook_trace_tests)

# N47K local-only bounded checkpoint inspection.
add_executable(qbrain_hook_diagnostic_tests tests/test_n47k.cpp)
target_compile_definitions(qbrain_hook_diagnostic_tests PRIVATE QBRAIN_DIAGNOSTIC_STANDALONE=1)
target_link_libraries(qbrain_hook_diagnostic_tests PRIVATE qbrain_memory)
add_test(NAME qbrain_hook_diagnostic_unit COMMAND qbrain_hook_diagnostic_tests)

# N47L: reuse the production fact-store dependency closure.
add_executable(qbrain_multiterm_tests tests/test_n47l.cpp)
target_compile_definitions(qbrain_multiterm_tests PRIVATE QBRAIN_MULTITERM_STANDALONE=1)
target_link_libraries(qbrain_multiterm_tests PRIVATE qbrain_mcp qbrain_ops qbrain_memory qbrain_core qbrain_search qbrain_jobs qbrain_ai)
add_test(NAME qbrain_multiterm_unit COMMAND qbrain_multiterm_tests)
