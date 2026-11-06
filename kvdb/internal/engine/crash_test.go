package engine

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"
)

// B1 to B3: a batch frame cut at EVERY length leaves none of its ops visible,
// and Open truncates the file back to the last good frame.
func TestBatchAllOrNothingEveryCut(t *testing.T) {
	base := append(makeHeader(), EncodeFrame(1, []Op{{Type: OpPut, Key: []byte("a"), Value: []byte("1")}})...)
	batch := EncodeFrame(2, []Op{
		{Type: OpPut, Key: []byte("b1"), Value: []byte("x")},
		{Type: OpPut, Key: []byte("b2"), Value: []byte("y")},
		{Type: OpDel, Key: []byte("a")},
	})
	for cut := 0; cut < len(batch); cut++ {
		path := filepath.Join(t.TempDir(), "t.db")
		os.WriteFile(path, append(append([]byte(nil), base...), batch[:cut]...), 0o644)
		d, err := Open(path, 0)
		if err != nil {
			t.Fatalf("cut %d: open failed: %v", cut, err)
		}
		if _, ok := d.Get([]byte("a")); !ok {
			t.Fatalf("cut %d: key a lost", cut)
		}
		if _, ok := d.Get([]byte("b1")); ok {
			t.Fatalf("cut %d: partial batch visible", cut)
		}
		d.Close()
		if st, _ := os.Stat(path); st.Size() != int64(len(base)) {
			t.Fatalf("cut %d: file size %d, want %d", cut, st.Size(), len(base))
		}
	}
}

// F4: file truncated by one byte. Open succeeds, only the last record is lost.
func TestTruncatedByOneByte(t *testing.T) {
	path := filepath.Join(t.TempDir(), "t.db")
	d, _ := Open(path, 0)
	d.Put([]byte("a"), []byte("1"))
	d.Put([]byte("b"), []byte("2"))
	d.Close()
	st, _ := os.Stat(path)
	os.Truncate(path, st.Size()-1)

	d, err := Open(path, 0)
	if err != nil {
		t.Fatalf("open after truncation: %v", err)
	}
	defer d.Close()
	if v, ok := d.Get([]byte("a")); !ok || string(v) != "1" {
		t.Fatal("a should survive")
	}
	if _, ok := d.Get([]byte("b")); ok {
		t.Fatal("b was torn and must be absent")
	}
}

// A5: no Close, as after kill -9. Put returns only after fsync, so a fresh
// Open of the same file must see the value.
func TestAckedWriteSurvivesWithoutClose(t *testing.T) {
	path := filepath.Join(t.TempDir(), "t.db")
	d, _ := Open(path, 0)
	if err := d.Put([]byte("k"), []byte("v")); err != nil {
		t.Fatal(err)
	}
	// deliberately no d.Close()
	d2, err := Open(path, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer d2.Close()
	if v, ok := d2.Get([]byte("k")); !ok || string(v) != "v" {
		t.Fatalf("acked write lost: %q %v", v, ok)
	}
	d.Close()
}

// B5: put X then delete X in one batch. Ops apply in order, X ends up absent,
// and it stays absent after reopen.
func TestBatchSameKeyOrderAfterReopen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "t.db")
	d, _ := Open(path, 0)
	d.Batch([]Op{
		{Type: OpPut, Key: []byte("x"), Value: []byte("1")},
		{Type: OpDel, Key: []byte("x")},
	})
	d.Close()
	d, _ = Open(path, 0)
	defer d.Close()
	if _, ok := d.Get([]byte("x")); ok {
		t.Fatal("x should be absent (last op wins)")
	}
}

// D1: two writers at once. Run with: go test -race ./...
func TestConcurrentWriters(t *testing.T) {
	path := filepath.Join(t.TempDir(), "t.db")
	d, _ := Open(path, 0)
	var wg sync.WaitGroup
	for w := 0; w < 2; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			for i := 0; i < 100; i++ {
				k := []byte(fmt.Sprintf("w%d-k%d", w, i))
				if err := d.Put(k, k); err != nil {
					t.Error(err)
					return
				}
			}
		}(w)
	}
	wg.Wait()
	d.Close()

	d, _ = Open(path, 0)
	defer d.Close()
	if d.Len() != 200 {
		t.Fatalf("want 200 keys, got %d", d.Len())
	}
}

// Limits from the spec.
func TestLimits(t *testing.T) {
	d := openTemp(t)
	big := bytes.Repeat([]byte{'k'}, MaxKeyLen+1)
	if err := d.Put(big, []byte("v")); err != ErrInvalidOp {
		t.Fatalf("key 1025B: got %v", err)
	}
	if err := d.Put([]byte("k"), make([]byte, MaxValueLen+1)); err != ErrInvalidOp {
		t.Fatalf("value >1MB: got %v", err)
	}
	if err := d.Put([]byte("k"), make([]byte, MaxValueLen)); err != nil {
		t.Fatalf("value of exactly 1MB should work: %v", err)
	}
	ops := make([]Op, MaxBatchOps+1)
	for i := range ops {
		ops[i] = Op{Type: OpPut, Key: []byte("k"), Value: []byte("v")}
	}
	if err := d.Batch(ops); err != ErrBatchSize {
		t.Fatalf("10001 ops: got %v", err)
	}
	if err := d.Batch([]Op{{Type: 9, Key: []byte("k")}}); err != ErrInvalidOp {
		t.Fatalf("bad op type: got %v", err)
	}
}