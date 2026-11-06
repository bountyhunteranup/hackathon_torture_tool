# KillDB Architecture

**Document status:** Increment 1 architecture  
**Implementation language:** Go 1.23+  
**Storage model:** Append-only write-ahead log (WAL) with an in-memory hash index

> This document describes the code that exists in Increment 1 and explicitly separates it from planned work. It does not claim that the current project already satisfies every hackathon requirement.

## 1. Project purpose

KillDB is an educational key-value database designed to explore persistence, crash recovery, atomic batches, concurrency, and failure testing.

The core design principle is:

- The WAL on persistent storage is the authoritative record of committed database transactions.
- The in-memory Go map is a derived index used for fast lookups.
- The index can be rebuilt by replaying valid WAL transactions during startup.

## 2. High-level architecture

```text
                 User / CLI
                     |
                     v
             cmd/killdb (CLI)
                     |
                     v
             internal/engine
              /           \
       WAL file          RAM index
       data.wal          map[string][]byte
              \           /
               Recovery
       (replay valid transactions)

       cmd/torture (currently scaffold only)
```

The engine owns the WAL file, the in-memory index, transaction sequence number, synchronization locks, and database lifecycle state.

## 3. Repository layout

```text
KillDB/
├── cmd/
│   ├── killdb/
│   │   └── main.go          # Command-line database interface
│   └── torture/
│       └── main.go          # Placeholder for the future torture controller
├── internal/
│   └── engine/
│       ├── engine.go        # WAL, API, recovery, index and locking
│       └── engine_test.go   # Engine tests
├── docs/
│   ├── INVARIANTS.md        # Initial correctness invariants
│   └── MICRO_STEPS.md       # Implementation roadmap
├── go.mod
├── README.md
└── ARCHITECTURE.md
```

Go's `internal` package boundary keeps the engine implementation private to this module's own application packages.

## 4. Current components

### 4.1 CLI (`cmd/killdb`)

The CLI parses a database directory and one command:

- `put KEY VALUE`
- `get KEY`
- `delete KEY`

It opens the engine, executes the command, prints a retrieved value or error, and closes the database. The current CLI does not yet expose a batch command.

Example:

```sh
go run ./cmd/killdb -dir ./data put name Anup
go run ./cmd/killdb -dir ./data get name
go run ./cmd/killdb -dir ./data delete name
```

### 4.2 Database engine (`internal/engine`)

The engine exposes `Open`, `Put`, `Get`, `Delete`, `Batch`, and `Close`.

Its main state is:

- An open WAL file handle.
- An in-memory `map[string][]byte` index.
- A monotonically increasing transaction sequence number.
- An `RWMutex` for coordinating readers and writers.
- Closed and poisoned state flags.

All write operations take the exclusive lock. Reads take the read lock. Values are copied at API boundaries so callers cannot mutate stored byte slices through shared references.

### 4.3 WAL (`data.wal`)

The current WAL is an append-only sequence of frames. Each frame has this binary envelope:

```text
+----------------------+----------------------+-------------------+
| payload length       | JSON transaction     | CRC32 checksum    |
| 4 bytes, big-endian  | variable length       | 4 bytes           |
+----------------------+----------------------+-------------------+
```

The JSON transaction contains:

- `sequence`: the expected next transaction number.
- `operations`: one or more PUT or DELETE operations.

A PUT contains a key and byte value. A DELETE contains a key and no value. An API batch is encoded as one transaction frame, not as a sequence of independently committed frames.

CRC32 is used to detect accidental frame corruption. It is not a cryptographic integrity mechanism.

### 4.4 In-memory index

The index is a Go map:

```go
map[string][]byte
```

It contains the latest value for each present key. A DELETE removes the key. The index is not independently persisted and is rebuilt from the WAL during `Open`.

### 4.5 Torture executable (`cmd/torture`)

At this increment, this is only a placeholder executable. It does not yet launch KillDB, generate workloads, kill processes, maintain an independent oracle, or verify recovery. Those functions are planned for a later increment.

## 5. Write path and acknowledgement rule

For `Put`, `Delete`, or `Batch`, the current engine performs the following steps while holding the exclusive mutex:

1. Reject a closed or poisoned database handle.
2. Validate the operation or operations.
3. Assign the next transaction sequence number.
4. Encode the transaction as JSON.
5. Build the frame: length, payload, checksum.
6. Append the complete frame using a write-full loop.
7. Call `File.Sync()` on the WAL.
8. Only if synchronization succeeds, apply the operations to the RAM index and advance the sequence number.
9. Return success.

If append or sync returns an error, the handle is marked poisoned. Further writes through that handle are rejected because the durable outcome may be uncertain; the caller must close and reopen the database to determine the recovered state.

The durability guarantee depends on the operating system, filesystem, storage device, and their implementation of sync semantics. A successful `File.Sync()` is the application's synchronization boundary; this implementation does not claim protection against every hardware or filesystem failure.

## 6. Read path

1. Acquire the read lock.
2. Reject a closed database handle.
3. Look up the key in the in-memory index.
4. Return `ErrNotFound` if the key is absent.
5. Otherwise return a copy of the value.

Reads use the in-memory index and do not scan the WAL.

## 7. Recovery path

`Open` creates or opens the database directory and WAL, initializes an empty index, and replays the WAL from the beginning.

For each frame, recovery:

1. Reads the 4-byte payload length.
2. Reads the declared payload and 4-byte checksum.
3. Verifies CRC32.
4. Decodes the JSON transaction.
5. Verifies that the sequence is exactly the previous sequence plus one.
6. Validates all operations.
7. Applies the transaction operations to the in-memory index.
8. Advances the recovered sequence number.

Tail handling:

- An incomplete trailing header, payload, or checksum is treated as a torn tail. Recovery truncates the WAL to the start of that incomplete frame and synchronizes the truncation.
- A complete frame with a checksum mismatch, malformed transaction, invalid operation, or sequence discontinuity causes `Open` to fail. The implementation does not silently skip complete corruption.

Because each batch is stored in one frame and applied only after the entire frame is decoded and validated, recovery applies a valid batch as one transaction.

## 8. Concurrency model

The current engine uses one `sync.RWMutex`:

- Writers (`Put`, `Delete`, `Batch`) take the exclusive lock. This serializes WAL appends, sequence assignment, sync, and index updates.
- Readers (`Get`) take a shared read lock and can run concurrently with other readers.
- A reader cannot observe an index update halfway through a write transaction.

This is a simple single-process concurrency model. Multi-process file locking and multiple independent database processes are not implemented.

## 9. Current invariants

1. The WAL is authoritative; the RAM index is derived and rebuildable.
2. A successful write API call means its complete transaction frame was appended and `File.Sync()` returned successfully before success was returned.
3. The index is changed only after the sync call succeeds.
4. One API batch is represented by one WAL frame and replayed as one transaction.
5. Valid WAL sequence numbers are contiguous and start at 1.
6. A partial trailing frame is not applied; it is truncated during open.
7. A complete frame with a bad checksum or invalid encoding is corruption; `Open` fails rather than silently skipping it.
8. An append or sync error poisons the current handle because the persistence outcome may be uncertain.
9. Writes are serialized; reads access the index under a read lock.

See [`docs/INVARIANTS.md`](docs/INVARIANTS.md) for the concise invariant list.

## 10. Current limitations and unimplemented work

The following are **not implemented in Increment 1**:

- Crash-safe compaction and generation switching.
- Independent torture controller, process launcher, randomized crash loop, and oracle.
- Explicit crash-injection hooks at every write/recovery boundary.
- Disk-full simulation and a complete disk-space policy.
- CLI batch interface.
- Enforced challenge limits for key size, value size, and batch size.
- Benchmarks and proof of one-million-key recovery within two seconds.
- Evidence for 500 randomized crash iterations.
- Multi-process coordination or distributed replication.
- Full power-loss guarantees across all filesystems and hardware.

These must be implemented and tested before claiming the corresponding challenge requirements are met.

## 11. Build and test commands

Run from the repository root:

```sh
go test ./...
go test -race ./...
go build ./cmd/killdb
go build ./cmd/torture
```

## 12. Planned architecture increments

1. **Torture protocol and oracle:** define a process protocol, independent expected-state model, acknowledgement tracking, reproducible random seeds, and restart verification.
2. **Crash injection:** add deterministic injection points around append, sync, index update, recovery, and compaction.
3. **Crash-safe compaction:** write and sync a new generation, atomically activate it, synchronize directory metadata where required, and retain/reconcile generations safely on restart.
4. **Failure handling:** add disk-full/error injection and bounded resource policies.
5. **Acceptance evidence:** benchmark limits, execute the required crash campaign, and document reproducible results.

The architecture document must be updated as these components become real; planned features must not be described as implemented until tests demonstrate them.
