package engine

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
)

const (
	fileMagic         = "KVDH"
	fileVersion uint16 = 1
	headerSize        = 8 // magic(4) + version(2) + reserved(2)

	MaxKeyLen   = 1024
	MaxValueLen = 1 << 20
	MaxBatchOps = 10000
)

var (
	ErrDiskFull   = errors.New("kvdb: max file size reached")
	ErrInvalidOp  = errors.New("kvdb: invalid operation (key 1-1024 bytes, value <= 1MB)")
	ErrBatchSize  = errors.New("kvdb: batch must have 1-10000 operations")
	ErrNotOurFile = errors.New("kvdb: not a kvdb file")
	ErrClosed     = errors.New("kvdb: database is closed")
	ErrFailed     = errors.New("kvdb: database failed; reopen to recover")
)

type DB struct {
	mu       sync.RWMutex // one global lock: writers exclusive, readers shared
	f        *os.File
	path     string
	size     int64 // end of the last valid frame
	maxBytes int64 // 0 = unlimited
	nextTxn  uint64
	index    map[string][]byte
	closed   bool
	failed   bool
}

func makeHeader() []byte {
	h := make([]byte, headerSize)
	copy(h, fileMagic)
	h[4] = byte(fileVersion)
	h[5] = byte(fileVersion >> 8)
	return h
}

func syncDir(dir string) error {
	if runtime.GOOS == "windows" {
		return nil // directories cannot be fsynced on Windows
	}
	d, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}

// Open opens or creates the database and runs recovery.
func Open(path string, maxBytes int64) (*DB, error) {
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE, 0o644)
	if err != nil {
		return nil, err
	}
	d := &DB{f: f, path: path, maxBytes: maxBytes, nextTxn: 1, index: make(map[string][]byte)}
	if err := d.recover(); err != nil {
		f.Close()
		return nil, err
	}
	return d, nil
}

// recover: validate header, replay frames until the first invalid one,
// truncate the torn tail, rebuild the index. It is idempotent: a crash at any
// point inside it leaves a file that the next recover() handles the same way.
func (d *DB) recover() error {
	data, err := io.ReadAll(d.f)
	if err != nil {
		return err
	}
	hdr := makeHeader()

	// New file, or a crash while the header was being written.
	if len(data) < headerSize {
		if !bytes.HasPrefix(hdr, data) {
			return ErrNotOurFile
		}
		if err := d.f.Truncate(0); err != nil {
			return err
		}
		if _, err := d.f.WriteAt(hdr, 0); err != nil {
			return err
		}
		if err := d.f.Sync(); err != nil {
			return err
		}
		if err := syncDir(filepath.Dir(d.path)); err != nil {
			return err
		}
		d.size = headerSize
		return nil
	}
	if !bytes.Equal(data[:headerSize], hdr) {
		return ErrNotOurFile
	}

	off := headerSize
	for off < len(data) {
		txn, ops, n, err := DecodeFrame(data[off:])
		if err != nil {
			break // torn or corrupt tail: everything from here is discarded
		}
		d.apply(ops)
		if txn >= d.nextTxn {
			d.nextTxn = txn + 1
		}
		off += n
	}
	if off < len(data) {
		if err := d.f.Truncate(int64(off)); err != nil {
			return err
		}
		if err := d.f.Sync(); err != nil {
			return err
		}
	}
	d.size = int64(off)
	return nil
}

// apply updates the in-memory index. Caller holds the write lock (or is recover).
func (d *DB) apply(ops []Op) {
	for _, op := range ops {
		switch op.Type {
		case OpPut:
			d.index[string(op.Key)] = append([]byte(nil), op.Value...)
		case OpDel:
			delete(d.index, string(op.Key))
		}
	}
}

func validate(ops []Op) error {
	if len(ops) == 0 || len(ops) > MaxBatchOps {
		return ErrBatchSize
	}
	for _, op := range ops {
		if len(op.Key) < 1 || len(op.Key) > MaxKeyLen || len(op.Value) > MaxValueLen {
			return ErrInvalidOp
		}
		if op.Type != OpPut && op.Type != OpDel {
			return ErrInvalidOp
		}
		if op.Type == OpDel && len(op.Value) != 0 {
			return ErrInvalidOp
		}
	}
	return nil
}

// Batch applies all ops atomically, in order (the last op on a key wins; this
// is the B5 rule: put X then delete X in one batch leaves X absent).
// Order: encode -> size check -> write -> fsync -> index -> return.
func (d *DB) Batch(ops []Op) error {
	if err := validate(ops); err != nil {
		return err
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.closed {
		return ErrClosed
	}
	if d.failed {
		return ErrFailed
	}

	frame := EncodeFrame(d.nextTxn, ops)
	if d.maxBytes > 0 && d.size+int64(len(frame)) > d.maxBytes {
		return ErrDiskFull // nothing was written
	}
	if _, err := d.f.WriteAt(frame, d.size); err != nil {
		return d.rollback(err)
	}
	if err := d.f.Sync(); err != nil {
		return d.rollback(err)
	}
	// The frame is durable. Only now do we change memory and report success.
	d.size += int64(len(frame))
	d.nextTxn++
	d.apply(ops)
	return nil
}

// rollback removes a partly written frame after a failed write or fsync.
func (d *DB) rollback(cause error) error {
	if err := d.f.Truncate(d.size); err != nil {
		d.failed = true
		return fmt.Errorf("kvdb: write failed (%v) and rollback failed: %w", cause, err)
	}
	return fmt.Errorf("kvdb: write failed: %w", cause)
}

func (d *DB) Put(key, value []byte) error {
	return d.Batch([]Op{{Type: OpPut, Key: key, Value: value}})
}

func (d *DB) Delete(key []byte) error {
	return d.Batch([]Op{{Type: OpDel, Key: key}})
}

// Get returns a copy of the value. A batch is applied under the write lock,
// so a reader sees the state before it or after it, never in between.
func (d *DB) Get(key []byte) ([]byte, bool) {
	d.mu.RLock()
	defer d.mu.RUnlock()
	if d.closed {
		return nil, false
	}
	v, ok := d.index[string(key)]
	if !ok {
		return nil, false
	}
	return append([]byte(nil), v...), true
}

func (d *DB) Len() int {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return len(d.index)
}

// Keys returns all keys sorted (for dump).
func (d *DB) Keys() []string {
	d.mu.RLock()
	defer d.mu.RUnlock()
	keys := make([]string, 0, len(d.index))
	for k := range d.index {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func (d *DB) Close() error {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.closed {
		return nil
	}
	d.closed = true
	if err := d.f.Sync(); err != nil {
		d.f.Close()
		return err
	}
	return d.f.Close()
}