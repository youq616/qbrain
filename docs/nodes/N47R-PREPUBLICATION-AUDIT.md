# N47R separate pre-publication outcome audit

2026-09-19. Reviewer: coordinating ChatGPT in a separate engineering self-review,
explicitly requested by the owner. No independent subagent or third-party reviewer.
Verdict: PASS to enable the fixed new prerelease. Public delivery is still pending.

## Actual read-only execution and recheck

Reviewed delivery commit c67e7799adae86929917ad0faffe99842d77a372,
tree713064092af6a3773f70644b21249f76c376fdba. Read-only run35430160564,
job105863178161, all required steps completed/success. It initially queued with
runner_id0; that was not a test failure or a PASS. No gate was bypassed while queued.

Artifact10580621876 downloaded:75391252bytes; SHA256
cfe6ec7e1457b4ef156773d0a666a852895fcf0bd73004ff6cc0fb6e3a937a5a.
All15outer members passed CRC, the1086-file delivery source tree reconstructs
exactly713064, and ordinary/optimized logs each show27test methods OK. Every one
of the five proposed assets matches its actual bytes and verification.json.

VALIDATION-EVIDENCE.zip contains all five original artifact ZIPs plus four metadata/
readback records (nine entries), not excerpts masquerading as complete evidence.
Its five raw archives match the fixed native/upgrade digests. The exact product is
4858530bytes, SHA256 e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5.
The guide is6143bytes, SHA2567db4673720d68d902555f72bbe778b0da3045c4c3b02cefa3717e3843b9e9b46.
Native and upgrade evidence verification was rerun in the current local process
against the original archives, and matched both CI receipts exactly. The27method
suite was also rerun normally and with-O in this continuation; both passed.
These are offline checks of actual Windows evidence, not new local Windows runs.

## Code/control-flow review

The release operation can only follow fresh authentication of both exact fixed
run attempts, all five exact job IDs, mandatory steps and five artifact IDs/hashes.
Canonical Linux source is Git-tree pinned before its validators load. Windows
archive differences are only the recorded exact LF->CRLF transform; untrusted
normalization, BOM changes and content edits reject. No original tests weakened.

The builder/installer/runtime and task tools have not changed since their fixed
native acceptance. Publication uploads the tested ZIP as-is under a clearer asset
name; it does not rebuild or repack it again. Metadata and evidence files may have
new delivery provenance/ZIP timestamps; they are verified as the actual uploaded
asset bytes, not falsely equated to prior read-only ancillary-file digests.

A new tag targets tested integration9e9, never latest main or the publisher commit.
Existing release/draft or wrong tag rejects. Draft ID comes from creation response.
Each upload ID/size/digest is pinned; downloads and state are rechecked before/after
visibility, then all five public URLs are anonymously read back. No destructive
fallback, tag movement or silent replacement exists. Non-latest/prerelease are
explicit; hashes do not constitute signing or atomic malicious-admin protection.

Only the explicit workflow permission/--publish change and this audit are enabled
now. Source hash pins remain. After publication success and receipt inspection,
restore the earlier read-only workflow. Do not alter the accepted ZIP or old N47O
assets to make their metadata look newer.

## Remaining scope

Public receipt and anonymous download success are not predeclared. Main/PR merge
identity must be recorded only after actual merge/tree recheck. No new C++/schema,
installer behavior, default consent, canonical operation ledger, user machine,
logged-in client, paid model, provider fees, real PG or signing result is claimed.
The native integrator and old-to-new upgrade scope passed; stable v1 and full
roadmap still require their separate external/user-visible effect gates.
