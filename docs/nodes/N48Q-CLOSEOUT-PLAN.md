# N48Q closeout review plan

2026-09-30. Owner authorizes continued development and a separate coordinator self-review. Runtime base: 4f8b470f32df106c9bb596f24252ffb800773b47 (tree 927600dc124416fe0701b03d21e28274f3e83b27). PR59 is not accepted or merged by this plan.

The chat execution container and Python currently fail before executing commands. GitHub write tools are available. Run the missing independent review on disposable native GitHub Actions runners; do not label CI as local or owner-machine execution. No real account, owner database, model request or release is involved.

Preserve the runtime and existing qualification tests. Add a separately written public-process reviewer and native Windows/Linux workflow. Each runner builds the exact checkout, executes original fact/context/session and core tests, then runs the additional reviewer on SQLite and a dedicated PostgreSQL database. Existing full regression results at the identical runtime base remain separately identified, not described as new runs.

Independent acceptance: complete original user quote and deterministic event/item/fact identities; source isolation; concurrent duplicate receipt reports create exactly one row; a changed fact revision invalidates an approved multi-fact receipt batch atomically; old paged receipts cannot be continued after state change; revoked receipts cannot be silently reactivated; forgetting one support keeps independently supported facts but changes the revision; forgetting the final support removes derived facts/relations/archive/use rows; replay cannot resurrect forgotten evidence. All requests/stdout/stderr and expected outcomes are retained. No test imports product or earlier fixture/reference code. Python -O must retain checks.

Use exact synthetic database names, native PG service, read-only Actions token, fixed checkout/upload actions and no downloaded private executables. Missing PG must fail, not skip. Record native build, test counts and tool hashes in logs and artifacts. Linux sanitizer execution supplements the Windows native run. Never erase a failed candidate or weaken an existing assertion to accept it.

Plan review by the coordinator: approved for this bounded supplementary implementation. It closes independent outcome validation for the existing fact module, not the still-absent PG Hook path, full tenant isolation, real host consumption, complete DLP or whole-project acceptance. Final verdict requires actually completed runs and a separate review of results/code. No PASS is declared now.
