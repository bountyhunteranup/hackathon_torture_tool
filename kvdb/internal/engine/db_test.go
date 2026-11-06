package engine

import (
	"path/filepath"
	"testing"
)

func openTemp(t *testing.T) *DB {
	t.Helper()
	db, err := Open(filepath.Join(t.TempDir(), "test.db"), 0)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestPutGet(t *testing.T) {
	db := openTemp(t)
	if err := db.Put([]byte("name"), []byte("Srinath")); err != nil {
		t.Fatal(err)
	}
	v, ok, err := db.Get([]byte("name"))
	if err != nil {
		t.Fatal(err)
	}
	if !ok || string(v) != "Srinath" {
		t.Fatalf("got %q ok=%v", v, ok)
	}
}

func TestGetMissing(t *testing.T) {
	db := openTemp(t)
	_, ok, _ := db.Get([]byte("ghost"))
	if ok {
		t.Fatal("expected miss")
	}
}

func TestDelete(t *testing.T) {
	db := openTemp(t)
	_ = db.Put([]byte("x"), []byte("1"))
	if err := db.Delete([]byte("x")); err != nil {
		t.Fatal(err)
	}
	_, ok, _ := db.Get([]byte("x"))
	if ok {
		t.Fatal("key should be gone after delete")
	}
}

func TestOverwrite(t *testing.T) {
	db := openTemp(t)
	_ = db.Put([]byte("k"), []byte("old"))
	_ = db.Put([]byte("k"), []byte("new"))
	v, ok, err := db.Get([]byte("k"))
	if err != nil {
		t.Fatal(err)
	}
	if !ok || string(v) != "new" {
		t.Fatalf("expected new, got %q", v)
	}
}

func TestBatch(t *testing.T) {
	db := openTemp(t)
	ops := []Op{
		{Type: OpPut, Key: []byte("a"), Value: []byte("1")},
		{Type: OpPut, Key: []byte("b"), Value: []byte("2")},
		{Type: OpDel, Key: []byte("a")},
	}
	if err := db.Batch(ops); err != nil {
		t.Fatal(err)
	}
	if _, ok, _ := db.Get([]byte("a")); ok {
		t.Fatal("a should be deleted")
	}
	v, ok, err := db.Get([]byte("b"))
	if err != nil {
		t.Fatal(err)
	}
	if !ok || string(v) != "2" {
		t.Fatalf("b: got %q ok=%v", v, ok)
	}
}

func TestPersistence(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "persist.db")

	db, _ := Open(path, 0)
	_ = db.Put([]byte("hello"), []byte("world"))
	db.Close()

	db2, err := Open(path, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer db2.Close()
	v, ok, err := db2.Get([]byte("hello"))
	if err != nil {
		t.Fatal(err)
	}
	if !ok || string(v) != "world" {
		t.Fatalf("after reopen: got %q ok=%v", v, ok)
	}
}

func TestLen(t *testing.T) {
	db := openTemp(t)
	_ = db.Put([]byte("a"), []byte("1"))
	_ = db.Put([]byte("b"), []byte("2"))
	_ = db.Delete([]byte("a"))
	if db.Len() != 1 {
		t.Fatalf("expected 1, got %d", db.Len())
	}
}

func TestKeys(t *testing.T) {
	db := openTemp(t)
	_ = db.Put([]byte("z"), []byte("1"))
	_ = db.Put([]byte("a"), []byte("2"))
	_ = db.Put([]byte("m"), []byte("3"))
	keys := db.Keys()
	if len(keys) != 3 || keys[0] != "a" || keys[1] != "m" || keys[2] != "z" {
		t.Fatalf("unexpected keys: %v", keys)
	}
}

func TestMaxBytes(t *testing.T) {
	// header(8) + frameHeader(12) + bodyFixed(12) + op(1+2+4+3+5) = 47 bytes minimum
	// set limit to exactly header size so any write is rejected
	db, err := Open(filepath.Join(t.TempDir(), "small.db"), headerSize)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	err = db.Put([]byte("key"), []byte("value"))
	if err != ErrDiskFull {
		t.Fatalf("expected ErrDiskFull, got %v", err)
	}
}

func TestClosedDB(t *testing.T) {
	db := openTemp(t)
	db.Close()
	if err := db.Put([]byte("k"), []byte("v")); err != ErrClosed {
		t.Fatalf("expected ErrClosed, got %v", err)
	}
}

func TestBatchValidation(t *testing.T) {
	db := openTemp(t)
	// empty batch
	if err := db.Batch(nil); err != ErrBatchSize {
		t.Fatalf("empty batch: expected ErrBatchSize, got %v", err)
	}
	// empty key
	if err := db.Batch([]Op{{Type: OpPut, Key: nil, Value: []byte("v")}}); err != ErrInvalidOp {
		t.Fatalf("nil key: expected ErrInvalidOp, got %v", err)
	}
}
