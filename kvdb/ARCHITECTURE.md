# Architecture

## Overview

kvdb is a crash-safe, append-only key-value database written in pure Go
(standard library only). One file holds everything. The in-memory index
maps keys to their value's location on disk — values are never stored in RAM.

---

## Project Layout

```
kvdb/
  cmd/
    kvdb/main.go          CLI + line-protocol server
    torture/main.go       Concurrent stress tester (disabled, pending update)
  internal/engine/
    format.go             Binary frame encode / decode + CRC
    format_test.go        Frame-level unit tests
    db.go                 DB struct: Open, Put, Get, Delete, Batch, Close
    db_test.go            Normal operation tests
    crash_test.go         Crash-safety and atomicity tests
  diagrams/               Architecture diagrams (future)
  go.mod
  Makefile / build.bat
  README.md
  ARCHITECTURE.md         (this file)
  BREAKING.md             Shortcomings tracker
  PROMPTS.md              Prompt history log
```

---

## On-Disk File Format

Every database is a single file with this layout:

```
┌─────────────────────────────────────────────────────┐
│  FILE HEADER  (8 bytes)                             │
│  magic "KVDH" (4) | version (2) | reserved (2)      │
├─────────────────────────────────────────────────────┤
│  FRAME 1                                            │
├─────────────────────────────────────────────────────┤
│  FRAME 2                                            │
├─────────────────────────────────────────────────────┤
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

### Frame Layout

Each frame is one atomic transaction — it contains one or more ops.

```
┌──────────────────────────────────────────────────────────────┐
│  FRAME HEADER  (12 bytes)                                    │
│  frameMagic 0x4B564442 (4) | bodyLen (4) | CRC32c (4)        │
├──────────────────────────────────────────────────────────────┤
│  BODY                                                        │
│  txnID (8) | opCount (4)                                     │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ OP 1: type (1) | keyLen (2) | valLen (4) | key | val │    │
│  ├──────────────────────────────────────────────────────┤    │
│  │ OP 2: ...                                            │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

- Op type: `0x01` = PUT, `0x02` = DELETE
- CRC32c covers the entire body (everything after the CRC field)
- All integers are little-endian

### Limits

| Property     | Limit         |
|--------------|---------------|
| Max key size | 1,024 bytes   |
| Max value size | 1 MB        |
| Max ops per batch | 10,000   |
| Max file size | configurable (0 = unlimited) |

---

## In-Memory Index

```
map[string]entry

type entry struct {
    off  int64   // absolute file offset of the value bytes
    vlen uint32  // length of the value in bytes
}
```

- Only keys and their disk locations are held in RAM — values are never cached
- RAM usage is O(number of keys), not O(total data size)
- On `Get`, the value is read from disk with a single `f.ReadAt(buf, entry.off)`

---

## Write Path (Batch)

```
validate(ops)
  │
  ▼
lock (exclusive)
  │
  ▼
EncodeFrame → [magic][bodyLen][CRC][txnID][ops...]
  │
  ▼
size check (maxBytes guard)
  │
  ▼
f.WriteAt(frame, d.size)   ← append to end of file
  │
  ▼
f.Sync()                   ← flush to disk (fsync)
  │
  ├── failure → rollback: f.Truncate(d.size)
  │
  ▼
d.size += len(frame)
d.nextTxn++
applyAt(ops, frameStart)   ← update in-memory index ONLY after fsync
  │
  ▼
unlock → return nil
```

A write is acknowledged to the caller only after `fsync` succeeds.
The index is updated only after the frame is durable on disk.

---

## Read Path (Get)

```
lock (shared / RLock)
  │
  ▼
index lookup: key → entry{off, vlen}
  │
  ├── miss → return nil, false, nil
  │
  ▼
f.ReadAt(buf, entry.off)   ← read value bytes directly from disk
  │
  ▼
unlock → return buf, true, nil
```

Reads and writes can overlap — `sync.RWMutex` allows multiple concurrent
readers. A reader always sees a consistent snapshot: either the state before
a batch or after it, never in between.

---

## Recovery (Open)

```
Open(path)
  │
  ▼
read 8-byte file header
  │
  ├── empty / partial header → write fresh header, fsync, syncDir
  ├── wrong magic            → ErrNotOurFile
  │
  ▼
seek to offset 8
bufio.Reader (64 KB buffer)
  │
  ▼
loop:
  Peek(12)              ← read frame header without consuming
  validate bodyLen      ← reject garbage / impossibly large values
  io.ReadFull(frame)    ← read full frame
  DecodeFrame + CRC     ← verify integrity
  applyAt(ops, off)     ← update index with disk offsets
  off += len(frame)
  │
  ├── any error → break (torn tail detected)
  │
  ▼
if file.Size() != off:
  f.Truncate(off)       ← discard torn tail
  f.Sync()
  │
  ▼
d.size = off
return db
```

Recovery is idempotent — a crash at any point during recovery leaves a file
that the next `Open` handles identically.

---

## Crash Safety Guarantees

| Scenario | Behaviour |
|----------|-----------|
| Process killed mid-write (kill -9) | Torn frame detected by CRC on next Open; truncated |
| File truncated by 1 byte | Last frame discarded; all prior frames intact |
| Batch cut at any byte offset | Entire batch invisible; prior state preserved |
| Put X then Del X in one batch | X is absent (last op in batch wins) |
| Acked write (Put returned nil) | Always visible after reopen — fsync happened before ACK |
| Concurrent writers | Global write lock ensures no interleaving |

---

## CLI Commands

```
kvdb <command> <path> [args] [--max-bytes N]
```

| Command | Description |
|---------|-------------|
| `open`  | Open DB, print key count and recovery time |
| `put`   | `put <path> <key> <value>` |
| `get`   | `get <path> <key>` |
| `del`   | `del <path> <key>` |
| `batch` | `batch <path> <file>` — reads ops from a file (one per line: `put k v` / `del k`) |
| `dump`  | Print all key-value pairs sorted by key |
| `check` | Read-only integrity scan — reports frame count and torn tail bytes |
| `serve` | Line-protocol server over stdin/stdout |

### Serve Protocol

```
<id> put <key> <value>
<id> del <key>
<id> get <key>
<id> batch put <k> <v> ; del <k> ; ...

Replies:
ACK <id>              write fsynced and applied
ERR <id> <message>    write rejected
VAL <id> <value>      get hit
NOTFOUND <id>         get miss
```

---

## Known Shortcomings

See [BREAKING.md](./BREAKING.md) for the full tracker.

| # | Shortcoming | Severity | Status |
|---|-------------|----------|--------|
| 1 | Full file loaded into RAM on Open | High | Fixed |
| 2 | No compaction — log grows forever | High | Open |
| 3 | Single global write lock | Medium | Open |
| 4 | Get silent on closed DB | Medium | Fixed |
| 5 | No key validation on Get | Low | Open |
| 6 | Double read on torn tail in recover | Low | Open |
| 7 | No syncDir on rollback | Low | Open |
| 8 | Keys() full alloc every call | Low | Open |
| 9 | maxBytes off by 8 bytes | Low | Open |
