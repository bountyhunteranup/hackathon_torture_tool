# Architecture

## Overview

```
cmd/kvdb/main.go       CLI entry point
cmd/torture/main.go    Stress/torture test tool
internal/engine/
  format.go            Binary frame encode/decode
  db.go                Core DB: Open, Put, Get, Delete, Batch, Close
```

## Storage Format

Each record is a fixed-header binary frame:

```
[1B type][4B key_len][4B val_len][key_bytes][val_bytes]
```

- type: 0x01 = PUT, 0x02 = DELETE
- Append-only log; latest entry for a key wins
- In-memory index maps key → file offset of latest record
