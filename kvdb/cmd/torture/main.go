package main

import (
	"fmt"
	"log"
	"math/rand"
	"os"
	"strconv"
	"sync"
	"time"

	"kvdb/internal/engine"
)

func main() {
	path := "torture.db"
	workers := 4
	ops := 1000
	if len(os.Args) > 1 {
		path = os.Args[1]
	}
	if len(os.Args) > 2 {
		workers, _ = strconv.Atoi(os.Args[2])
	}
	if len(os.Args) > 3 {
		ops, _ = strconv.Atoi(os.Args[3])
	}

	db, err := engine.Open(path)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	var wg sync.WaitGroup
	start := time.Now()
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			r := rand.New(rand.NewSource(time.Now().UnixNano()))
			for i := 0; i < ops; i++ {
				key := fmt.Sprintf("key-%d-%d", id, r.Intn(100))
				val := fmt.Sprintf("val-%d", r.Intn(1000))
				switch r.Intn(3) {
				case 0:
					_ = db.Put(key, val)
				case 1:
					_, _ = db.Get(key)
				case 2:
					_ = db.Delete(key)
				}
			}
		}(w)
	}
	wg.Wait()
	elapsed := time.Since(start)
	total := workers * ops
	fmt.Printf("done: %d ops in %s (%.0f ops/s)\n", total, elapsed, float64(total)/elapsed.Seconds())

	if err := db.Check(); err != nil {
		log.Fatalf("check failed: %v", err)
	}
	fmt.Println("integrity check: ok")
}
