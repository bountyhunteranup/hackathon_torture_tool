# kvdb

A simple key-value database engine written in Go.

## Commands

| Command | Description |
|---------|-------------|
| `open`  | Open a database file |
| `put`   | Insert or update a key-value pair |
| `get`   | Retrieve a value by key |
| `del`   | Delete a key |
| `batch` | Execute multiple operations atomically |
| `dump`  | Dump all key-value pairs |
| `check` | Verify database integrity |
| `serve` | Start HTTP API server |

## Build

```bash
make
```

Produces `./kvdb` and `./torture` binaries.
