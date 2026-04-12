# Path A Failure Drills

- `searx_failure` => status `source_error` reason `simulated_searx_failure`
- `reader_failure` => status `reader_error` reason `simulated_reader_failure`
- `storage_failure` => status `storage_error` reason `simulated_storage_error`

Expected terminal statuses:
- SearXNG failure => `source_error`
- Reader failure => `reader_error`
- Storage failure => `storage_error`
