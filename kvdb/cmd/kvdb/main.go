package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"kvdb/internal/engine"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

// parseMaxBytes removes "--max-bytes N" from args wherever it appears.
func parseMaxBytes(args []string) ([]string, int64, error) {
	var rest []string
	var max int64
	for i := 0; i < len(args); i++ {
		if args[i] == "--max-bytes" {
			if i+1 >= len(args) {
				return nil, 0, fmt.Errorf("--max-bytes needs a value")
			}
			n, err := strconv.ParseInt(args[i+1], 10, 64)
			if err != nil || n < 0 {
				return nil, 0, fmt.Errorf("bad --max-bytes value %q", args[i+1])
			}
			max = n
			i++
			continue
		}
		rest = append(rest, args[i])
	}
	return rest, max, nil
}

const usage = "usage: kvdb <open|put|get|del|batch|dump|check|serve> <path> [args] [--max-bytes N]"

func run(argv []string) error {
	args, maxBytes, err := parseMaxBytes(argv)
	if err != nil {
		return err
	}
	if len(args) < 2 {
		return fmt.Errorf(usage)
	}
	cmd, path, rest := args[0], args[1], args[2:]

	if cmd == "check" { // read-only, does not run recovery
		frames, tail, err := engine.CheckFile(path)
		if err != nil {
			return err
		}
		if tail == 0 {
			fmt.Printf("OK (%d frames)\n", frames)
		} else {
			fmt.Printf("OK (%d frames; %d trailing bytes are a torn tail that open will discard)\n", frames, tail)
		}
		return nil
	}

	start := time.Now()
	db, err := engine.Open(path, maxBytes) // Open runs recovery
	if err != nil {
		return err
	}
	recovery := time.Since(start)
	defer db.Close()

	switch cmd {
	case "open":
		fmt.Printf("keys=%d recovery_ms=%.2f\n", db.Len(), float64(recovery.Microseconds())/1000)
	case "put":
		if len(rest) != 2 {
			return fmt.Errorf("put <path> <key> <value>")
		}
		return db.Put([]byte(rest[0]), []byte(rest[1]))
	case "get":
		if len(rest) != 1 {
			return fmt.Errorf("get <path> <key>")
		}
		if v, ok := db.Get([]byte(rest[0])); ok {
			fmt.Println(string(v))
		} else {
			fmt.Println("NOTFOUND")
		}
	case "del":
		if len(rest) != 1 {
			return fmt.Errorf("del <path> <key>")
		}
		return db.Delete([]byte(rest[0]))
	case "batch":
		if len(rest) != 1 {
			return fmt.Errorf("batch <path> <file>")
		}
		ops, err := readBatchFile(rest[0])
		if err != nil {
			return err
		}
		return db.Batch(ops)
	case "dump":
		for _, k := range db.Keys() { // Keys() is sorted
			v, _ := db.Get([]byte(k))
			fmt.Printf("%s\t%s\n", k, v)
		}
	case "serve":
		return serve(db)
	default:
		return fmt.Errorf("unknown command %q\n%s", cmd, usage)
	}
	return nil
}

// parseOp parses "put <key> <value>" (value may contain spaces, may be empty)
// or "del <key>".
func parseOp(s string) (engine.Op, error) {
	parts := strings.SplitN(strings.TrimSpace(s), " ", 3)
	switch {
	case parts[0] == "put" && len(parts) >= 2:
		op := engine.Op{Type: engine.OpPut, Key: []byte(parts[1])}
		if len(parts) == 3 {
			op.Value = []byte(parts[2])
		}
		return op, nil
	case parts[0] == "del" && len(parts) == 2:
		return engine.Op{Type: engine.OpDel, Key: []byte(parts[1])}, nil
	}
	return engine.Op{}, fmt.Errorf("bad op %q", s)
}

func readBatchFile(path string) ([]engine.Op, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var ops []engine.Op
	r := bufio.NewReaderSize(f, 1<<20)
	for {
		line, err := r.ReadString('\n')
		if err != nil && line == "" {
			break
		}
		if line = strings.TrimRight(line, "\r\n"); line != "" {
			op, perr := parseOp(line)
			if perr != nil {
				return nil, perr
			}
			ops = append(ops, op)
		}
		if err != nil {
			break
		}
	}
	return ops, nil
}

// serve reads one request per line from stdin and prints a reply per line to
// stdout. Protocol (one line each, <id> is chosen by the client):
//
//	<id> put <key> <value>
//	<id> del <key>
//	<id> batch put <k> <v> ; del <k> ; put <k> <v> ...
//	<id> get <key>
//
// Replies:
//
//	ACK <id>          only AFTER the operation is fsynced to disk
//	ERR <id> <msg>    the operation was not applied
//	VAL <id> <value> / NOTFOUND <id>     for get
//
// Keys and values must not contain newlines; inside a batch they must not
// contain ';'. Each line is handled in its own goroutine, so a client with two
// writers gets real concurrency (the DB's global lock keeps it safe).
func serve(db *engine.DB) error {
	var outMu sync.Mutex
	reply := func(s string) {
		outMu.Lock()
		fmt.Fprintln(os.Stdout, s) // os.Stdout is unbuffered
		outMu.Unlock()
	}
	var wg sync.WaitGroup
	r := bufio.NewReaderSize(os.Stdin, 1<<20)
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			break // EOF; a final line with no newline may be torn, so drop it
		}
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			continue
		}
		wg.Add(1)
		go func(l string) {
			defer wg.Done()
			handle(db, l, reply)
		}(line)
	}
	wg.Wait()
	return nil
}

func handle(db *engine.DB, line string, reply func(string)) {
	id, rest, _ := strings.Cut(line, " ")
	if key, ok := strings.CutPrefix(rest, "get "); ok {
		if v, found := db.Get([]byte(key)); found {
			reply("VAL " + id + " " + string(v))
		} else {
			reply("NOTFOUND " + id)
		}
		return
	}
	var ops []engine.Op
	var err error
	if body, ok := strings.CutPrefix(rest, "batch "); ok {
		for _, part := range strings.Split(body, ";") {
			var op engine.Op
			if op, err = parseOp(part); err != nil {
				break
			}
			ops = append(ops, op)
		}
	} else {
		var op engine.Op
		if op, err = parseOp(rest); err == nil {
			ops = []engine.Op{op}
		}
	}
	if err == nil {
		err = db.Batch(ops) // returns only after write + fsync
	}
	if err != nil {
		reply("ERR " + id + " " + strings.ReplaceAll(err.Error(), "\n", " "))
		return
	}
	reply("ACK " + id)
}