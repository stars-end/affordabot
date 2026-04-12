# Path A Failure Drills

## Warm-State Failures (after successful baseline run)

- `searx_failure` => status `source_error` reason `simulated_searx_failure` objects `3`
- `reader_failure` => status `reader_error` reason `simulated_reader_failure` objects `3`
- `storage_failure` => status `storage_error` reason `simulated_storage_error` objects `3`

## Cold-State Failures (isolated fresh state per drill)

- `searx_failure` => status `source_error` reason `simulated_searx_failure` objects `0` state_dir `docs/poc/windmill-storage-bakeoff/path-a-direct-storage/runtime_state__cold_searx_failure`
- `reader_failure` => status `reader_error` reason `simulated_reader_failure` objects `1` state_dir `docs/poc/windmill-storage-bakeoff/path-a-direct-storage/runtime_state__cold_reader_failure`
- `storage_failure` => status `storage_error` reason `simulated_storage_error` objects `0` state_dir `docs/poc/windmill-storage-bakeoff/path-a-direct-storage/runtime_state__cold_storage_failure`

Expected terminal statuses:
- SearXNG failure => `source_error`
- Reader failure => `reader_error`
- Storage failure => `storage_error`
