#pragma once
#include "qbrain/jobs/minions.hpp"

namespace qbrain::jobs {
// Executes an already claimed embedding job and owns its terminal/progress
// transitions. Returns only rows committed by this invocation, even on a
// partial failure. A lost claim never updates the new owner's job state.
int execute_embedding_job(Brain& brain, const Job& job);
// Automatic drain retains its historical all-queue selection and chunk-count
// return value. Generic drain_jobs continues to count processed jobs instead.
int drain_embedding_jobs(Brain& brain, int max_jobs);
std::string new_embedding_claim_token();
}  // namespace qbrain::jobs
