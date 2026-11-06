# Prompts Log

| # | Time (UTC) | Model | Prompt |
|---|-----------|-------|--------|
| 1 | 2025-07-15T00:00:00Z | Amazon Q (Claude 3.5 Sonnet) | Create kvdb/ architecture with go.mod, README.md, PROMPTS.md, BREAKING.md, ARCHITECTURE.md, diagrams/, cmd/kvdb/main.go (CLI: open, put, get, del, batch, dump, check, serve), cmd/torture/main.go (torture tool), internal/engine/format.go, format_test.go, db.go, and Makefile that builds ./kvdb and ./torture |
| 2 | 2025-07-15T00:05:00Z | Amazon Q (Claude 3.5 Sonnet) | "make I don't have it" — replaced Makefile with build.bat using go build directly, built kvdb.exe and torture.exe successfully |
| 3 | 2025-07-15T00:10:00Z | Amazon Q (Claude 3.5 Sonnet) | "Now kvdb.exe" — ran smoke test, fixed log.Fatal(nil) bug in put/del/batch commands, verified put/get/dump/check all work |
| 4 | 2025-07-15T00:15:00Z | Amazon Q (Claude 3.5 Sonnet) | Hackathon compliance check: classify all imports (stdlib/own/third-party), flag banned libs, identify what creates test.db, advise on t.TempDir() for tests |
| 5 | 2025-07-15T00:20:00Z | Amazon Q (Claude 3.5 Sonnet) | "can you check the code What I have given" — ran full code review on kvdb/ folder, no issues found |
| 6 | 2025-07-15T00:25:00Z | Amazon Q (Claude 3.5 Sonnet) | "What are the shortcomings in this" — analyzed db.go and format.go, identified 9 shortcomings including full file RAM load, no compaction, single global lock, silent Get on closed DB, missing validation, double read on torn tail, missing syncDir on rollback, Keys() full alloc, maxBytes off by 8 |
| 7 | 2025-07-15T00:30:00Z | Amazon Q (Claude 3.5 Sonnet) | "I want to test the format and db" — created db_test.go with 11 tests (PutGet, GetMissing, Delete, Overwrite, Batch, Persistence, Len, Keys, MaxBytes, ClosedDB, BatchValidation), fixed TestMaxBytes limit, all 16 tests pass |
| 8 | 2025-07-15T00:35:00Z | Amazon Q (Claude 3.5 Sonnet) | "Can you test the crash_test.go don't change run it and tell me the result" — ran all 6 crash tests, all passed (race detector skipped, CGO disabled) |
