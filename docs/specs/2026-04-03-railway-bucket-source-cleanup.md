# Railway Bucket Service Source Cleanup (bd-85bn)

Date: 2026-04-03  
Scope: Affordabot dev Bucket/MinIO service source-control drift

## Runtime Truth (Current)
- `MINIO_URL=http://bucket.railway.internal:9000`
- `RAILWAY_SERVICE_BUCKET_URL=<bucket-service-domain>.up.railway.app` (observed example on 2026-04-03: `bucket-dev-2f3a.up.railway.app`)
- Runtime also exposes Railway S3/AWS-style vars: `S3_ENDPOINT`, `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- MinIO-style vars remain supported by app/runtime fallback: `MINIO_*`
- Storage-backed substrate runs are passing integrity checks

## Decision
Treat the Railway Bucket service as an infra service, not an app repo deployment target.

The `railwayapp-templates/minio` source attachment is stale metadata (`GitHub Repo not found`) and should be removed so operators do not interpret it as a required code source.

## Automation Viability Check

### CLI viability: not automatable
The available Railway CLI command surface for existing services does not expose source disconnect/update:

- `railway service --help` => `link`, `status`, `logs`, `redeploy`, `restart`, `scale`
- `railway project --help` => `list`, `link`, `delete`
- `railway add --help` includes `--repo` only for creating a new service

There is no safe, documented CLI command to disconnect an existing service source repo.

### API viability: not safe to automate in this lane
`railway status --json` exposes read-only source metadata (`source.repo`) and confirms drift, but write-path mutations for source unlink are not available through a documented/stable CLI contract in this repo.

Using undocumented GraphQL mutations to mutate service source metadata is high-risk and may trigger unintended deploy behavior. This lane therefore treats source unlink as manual-only.

### Read-only audit command (automated evidence)
Run:

```bash
./scripts/dx-load-auth.sh -- python scripts/maintenance/audit_bucket_source_link.py \
  --project 1ed20f8a-aeb7-4de6-a02c-8851fff50d4e \
  --environment dev \
  --service Bucket
```

Exit codes:
- `0`: no stale template source link detected
- `2`: stale template link detected (`railwayapp-templates/minio`), manual UI disconnect required
- `1`: command/runtime failure

## Required Manual Operator Action (Railway UI)
1. Open Railway project `affordabot` → service `Bucket` → `Settings`.
2. In the **Source** section where `railwayapp-templates/minio` shows `GitHub Repo not found`, click **Disconnect** (or **Remove Repository**).
3. Leave the service unlinked from GitHub after disconnecting.

## Post-Action Verification
- `Settings → Source` no longer shows a broken GitHub repository.
- Bucket service remains healthy/running.
- Backend storage checks still pass using existing env vars.
