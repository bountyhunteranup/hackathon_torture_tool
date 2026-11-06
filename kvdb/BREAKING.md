# BREAKING CHANGES

## v0.1.0
- Initial release

## Shortcomings Tracker

| # | Found On | Shortcoming | Severity | Status |
|---|----------|-------------|----------|--------|
| 1 | 2025-07-15T00:25:00Z | Full file loaded into RAM on Open (io.ReadAll) | High | Open |
| 2 | 2025-07-15T00:25:00Z | No compaction — log grows forever | High | Open |
| 3 | 2025-07-15T00:25:00Z | Single global write lock kills concurrency | Medium | Open |
| 4 | 2025-07-15T00:25:00Z | Get returns nil,false on closed DB — silent failure | Medium | Open |
| 5 | 2025-07-15T00:25:00Z | No key validation on Get | Low | Open |
| 6 | 2025-07-15T00:25:00Z | recover() reads whole file twice on torn tail | Low | Open |
| 7 | 2025-07-15T00:25:00Z | No syncDir on rollback | Low | Open |
| 8 | 2025-07-15T00:25:00Z | Keys() allocates full sorted slice every call | Low | Open |
| 9 | 2025-07-15T00:25:00Z | maxBytes off by 8 bytes (header not accounted) | Low | Open |
