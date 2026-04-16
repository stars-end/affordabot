# dx-review: Economic Pipeline Architecture POC

Date: 2026-04-14
Beads: `bd-2agbe.7`
PR: https://github.com/stars-end/affordabot/pull/436
Reviewed head: `b5ee08c21b35bc20ccf087ea606b03a3f6bbf188`

## Command

```bash
dx-review run \
  --beads bd-2agbe.7 \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --pr https://github.com/stars-end/affordabot/pull/436 \
  --template architecture-review \
  --read-only-shell \
  --wait \
  --timeout-sec 1200
```

## Quorum Result

Partial success:

- Claude/Opus reviewer: `pass_with_findings`
- GLM reviewer: failed before review output because `cc-glm` could not resolve `op://dev/Agent-Secrets-Production/ZAI_API_KEY`
- Effective quorum: `1/2 completed`

Local report files:

- `/tmp/dx-review/bd-2agbe.7/summary.md`
- `/tmp/dx-review/bd-2agbe.7/summary.json`
- `/tmp/dx-runner/claude-code/bd-2agbe.7.claude.log`
- `/tmp/dx-runner/cc-glm/bd-2agbe.7.glm.log`

## Reviewer Verdict

Claude/Opus verdict: `pass_with_findings`.

High-signal findings:

1. Verification scripts use raw `dict[str, Any]` fixtures instead of validating against `backend/schemas/economic_evidence.py` Pydantic models. This creates schema/verifier drift risk.
2. `schemas.economic_evidence.MechanismFamily` overlaps with `schemas.analysis.ImpactMode`, but there is no explicit mapping. The pass-through naming differs: `FEE_OR_TAX_PASS_THROUGH` vs `PASS_THROUGH_INCIDENCE`.
3. Verification scripts duplicate utility helpers. Acceptable for POC, but should be consolidated before adding many more scripts.
4. Dynamic `importlib` test loading is fragile but acceptable for script-local POCs.
5. Some overlay scripts depend on generated artifacts from prior POC commits; this should stay visible if artifacts are moved.

## Action Taken

The next POC wave explicitly incorporates the two medium findings:

- `bd-2agbe.11`: scrape + structured integration must validate ready evidence against `schemas.economic_evidence` where possible and include an `ImpactMode` to `MechanismFamily` mapping.
- `bd-2agbe.12`: source/API expansion matrix must identify whether source expansion changes key strategy or mechanism mapping assumptions.

## DX Friction

`dx-review doctor` passed for `cc-glm-review`, but the actual run failed resolving the Z.ai token through `op://`.

This is important because the run looked healthy at preflight and only failed after launch. Product-agent usage would be better if `dx-review doctor` exercised the same token resolution path as the live review process.

Suggested DX follow-up:

- make `dx-review doctor --worktree` validate the exact `cc-glm-headless` token resolution path, not only adapter/model metadata;
- surface the failed secret URI category without printing values;
- classify this failure as `secret_auth_resolution_failed_after_preflight`.
