package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"kvdb/internal/engine"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintln(os.Stderr, "usage: kvdb <file> <command> [args...]")
		os.Exit(1)
	}
	path, cmd := os.Args[1], os.Args[2]
	args := os.Args[3:]

	db, err := engine.Open(path)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	switch cmd {
	case "put":
		if len(args) != 2 {
			log.Fatal("put <key> <value>")
		}
		if err := db.Put(args[0], args[1]); err != nil {
			log.Fatal(err)
		}
	case "get":
		if len(args) != 1 {
			log.Fatal("get <key>")
		}
		v, err := db.Get(args[0])
		if err != nil {
			log.Fatal(err)
		}
		fmt.Println(v)
	case "del":
		if len(args) != 1 {
			log.Fatal("del <key>")
		}
		if err := db.Delete(args[0]); err != nil {
			log.Fatal(err)
		}
	case "batch":
		// args: put key val | del key  separated by commas via multiple args pairs
		// format: put k v del k put k v ...
		var ops []engine.BatchOp
		for i := 0; i < len(args); {
			switch args[i] {
			case "put":
				ops = append(ops, engine.BatchOp{Key: args[i+1], Value: args[i+2]})
				i += 3
			case "del":
				ops = append(ops, engine.BatchOp{Delete: true, Key: args[i+1]})
				i += 2
			default:
				log.Fatalf("unknown batch op: %s", args[i])
			}
		}
		if err := db.Batch(ops); err != nil {
			log.Fatal(err)
		}
	case "dump":
		for k, v := range db.Dump() {
			fmt.Printf("%s\t%s\n", k, v)
		}
	case "check":
		if err := db.Check(); err != nil {
			log.Fatal(err)
		}
		fmt.Println("ok")
	case "serve":
		addr := ":8080"
		if len(args) > 0 {
			addr = args[0]
		}
		serve(db, addr)
	default:
		log.Fatalf("unknown command: %s", cmd)
	}
}

func serve(db *engine.DB, addr string) {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		key := strings.TrimPrefix(r.URL.Path, "/")
		switch r.Method {
		case http.MethodGet:
			v, err := db.Get(key)
			if err != nil {
				http.Error(w, err.Error(), http.StatusNotFound)
				return
			}
			fmt.Fprint(w, v)
		case http.MethodPut:
			var body struct{ Value string }
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			if err := db.Put(key, body.Value); err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.WriteHeader(http.StatusNoContent)
		case http.MethodDelete:
			if err := db.Delete(key); err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
	log.Printf("serving on %s", addr)
	log.Fatal(http.ListenAndServe(addr, nil))
}
