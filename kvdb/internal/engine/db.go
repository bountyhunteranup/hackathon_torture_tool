package engine

import (
	"bufio"
	"bytes"
	"encoding/binary"
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

	// Checkpoint thresholds: write a checkpoint every 4 MB written or 10 000 ops.
	ckptEveryBytes int64 = 4 * 1024 * 1024
	ckptEveryOps   int   = 10_000
)

var (
	ErrDiskFull   = errors.New("kvdb: max file size reached")
	ErrInvalidOp  = errors.New("kvdb: invalid operation (key 1-1024 bytes, value <= 1MB)")
	ErrBatchSize  = errors.New("kvdb: batch must have 1-10000 operations")
	ErrNotOurFile = errors.New("kvdb: not a kvdb file")
	ErrClosed     = errors.New("kvdb: database is closed")
	ErrFailed     = errors.New("kvdb: database failed; reopen to recover")
)

// entry points at a value's bytes on disk.
type entry struct {
	off  int64  // absolute file offset of the value bytes
	vlen uint32 // length of the value
}

type DB struct {
	mu           sync.RWMutex
	f            *os.File
	path         string
	size         int64
	maxBytes     int64
	nextTxn      uint64
	index        map[string]entry
	liveBytes    int64
	lastCkptOff  int64 // file offset of the last valid checkpoint frame (0 = none)
	bytesSinceCkpt int64 // bytes written since last checkpoint
	opsSinceCkpt   int   // ops written since last checkpoint
	closed       bool
	failed       bool
}

func tmpPath(path string) string { return path + ".compact.tmp" }

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
// Any leftover .compact.tmp from a previous crashed Compact is removed first.
func Open(path string, maxBytes int64) (*DB, error) {
	// Req 4: delete leftover temp file before recovery so it can never be
	// mistaken for the real database.
	_ = os.Remove(tmpPath(path))

	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE, 0o644)
	if err != nil {
		return nil, err
	}
	d := &DB{f: f, path: path, maxBytes: maxBytes, nextTxn: 1, index: make(map[string]entry)}
	if err := d.recover(); err != nil {
		f.Close()
		return nil, err
	}
	return d, nil
}

// recover: validate header, find the latest valid checkpoint, load it,
// then replay only the frames that follow it.
func (d *DB) recover() error {
	// ── header ───────────────────────────────────────────────────────────────────────────
	hdr := makeHeader()
	var peek [headerSize]byte
	n, err := io.ReadFull(d.f, peek[:])
	if err != nil && err != io.ErrUnexpectedEOF && err != io.EOF {
		return err
	}
	if n < headerSize {
		if !bytes.HasPrefix(hdr, peek[:n]) {
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
	if !bytes.Equal(peek[:], hdr) {
		return ErrNotOurFile
	}

	// ── pass 1: scan all frames, record the offset of every valid checkpoint ───
	type ckptCandidate struct {
		off     int64
		txnID   uint64
		entries []CheckpointEntry
	}
	var (
		candidates []ckptCandidate
		validEnd   int64 = int64(headerSize) // last byte after the last good frame
	)
	{
		if _, err := d.f.Seek(int64(headerSize), io.SeekStart); err != nil {
			return err
		}
		br := bufio.NewReaderSize(d.f, 64*1024)
		off := int64(headerSize)
		for {
			peeked, err := br.Peek(frameHeaderSize)
			if err != nil {
				break
			}
			bodyLen := int(binary.LittleEndian.Uint32(peeked[4:]))
			if bodyLen < bodyFixedSize || bodyLen > frameHeaderSize+MaxBatchOps*(1+2+4+MaxKeyLen+MaxValueLen) {
				break
			}
			total := frameHeaderSize + bodyLen
			buf := make([]byte, total)
			if _, err := io.ReadFull(br, buf); err != nil {
				break
			}
			// Try checkpoint first, then normal frame.
			if txn, entries, cerr := DecodeCheckpoint(buf); cerr == nil {
				candidates = append(candidates, ckptCandidate{off: off, txnID: txn, entries: entries})
			} else {
				_, _, fn, ferr := DecodeFrame(buf)
				if ferr != nil || fn != total {
					break
				}
			}
			validEnd = off + int64(total)
			off = validEnd
		}
	}

	// ── pass 2: load latest valid checkpoint, replay frames after it ─────────
	replayFrom := int64(headerSize)
	for i := len(candidates) - 1; i >= 0; i-- {
		c := candidates[i]
		// Validate that every entry's offset is within the file.
		valid := true
		for _, e := range c.entries {
			if e.Off < int64(headerSize) || e.Off+int64(e.Vlen) > validEnd {
				valid = false
				break
			}
		}
		if !valid {
			continue
		}
		// Good checkpoint: seed the index from it.
		d.index = make(map[string]entry, len(c.entries))
		d.liveBytes = 0
		for _, e := range c.entries {
			key := string(e.Key)
			d.index[key] = entry{off: e.Off, vlen: e.Vlen}
			d.liveBytes += int64(e.Vlen)
		}
		d.lastCkptOff = c.off
		if c.txnID >= d.nextTxn {
			d.nextTxn = c.txnID + 1
		}
		// Replay starts at the frame immediately after this checkpoint.
		replayFrom = c.off + int64(frameHeaderSize) + int64(binary.LittleEndian.Uint32(
			func() []byte {
				// Re-read the bodyLen from the checkpoint frame header on disk.
				var hdr4 [4]byte
				d.f.ReadAt(hdr4[:], c.off+4)
				return hdr4[:]
			}(),
		))
		break
	}

	// ── pass 3: replay data frames from replayFrom to validEnd ──────────────
	if _, err := d.f.Seek(replayFrom, io.SeekStart); err != nil {
		return err
	}
	br2 := bufio.NewReaderSize(d.f, 64*1024)
	off := replayFrom
	for off < validEnd {
		peeked, err := br2.Peek(frameHeaderSize)
		if err != nil {
			break
		}
		bodyLen := int(binary.LittleEndian.Uint32(peeked[4:]))
		if bodyLen < bodyFixedSize || bodyLen > frameHeaderSize+MaxBatchOps*(1+2+4+MaxKeyLen+MaxValueLen) {
			break
		}
		total := frameHeaderSize + bodyLen
		buf := make([]byte, total)
		if _, err := io.ReadFull(br2, buf); err != nil {
			break
		}
		// Skip checkpoint frames during replay — already loaded above.
		if _, _, cerr := DecodeCheckpoint(buf); cerr == nil {
			off += int64(total)
			continue
		}
		txn, ops, fn, ferr := DecodeFrame(buf)
		if ferr != nil || fn != total {
			break
		}
		d.applyAt(ops, off, buf)
		if txn >= d.nextTxn {
			d.nextTxn = txn + 1
		}
		off += int64(total)
	}

	// ── truncate torn tail ─────────────────────────────────────────────────────────────────
	if fi, err := d.f.Stat(); err == nil && fi.Size() != validEnd {
		if err := d.f.Truncate(validEnd); err != nil {
			return err
		}
		if err := d.f.Sync(); err != nil {
			return err
		}
	}
	d.size = validEnd
	return nil
}

// applyAt updates the index using absolute file offsets and maintains liveBytes.
func (d *DB) applyAt(ops []Op, frameStart int64, frame []byte) {
	_, decoded, _, err := DecodeFrame(frame)
	if err != nil {
		return
	}
	for _, op := range decoded {
		switch op.Type {
		case OpPut:
			// Evict old live bytes for this key if it already existed.
			if prev, ok := d.index[string(op.Key)]; ok {
				d.liveBytes -= int64(prev.vlen)
			}
			e := entry{
				off:  frameStart + int64(op.ValOff),
				vlen: uint32(len(op.Value)),
			}
			d.index[string(op.Key)] = e
			d.liveBytes += int64(e.vlen)
		case OpDel:
			if prev, ok := d.index[string(op.Key)]; ok {
				d.liveBytes -= int64(prev.vlen)
			}
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
		return ErrDiskFull
	}
	// Pre-compute where each op's value will land on disk.
	frameStart := d.size
	if _, err := d.f.WriteAt(frame, frameStart); err != nil {
		return d.rollback(err)
	}
	if err := d.f.Sync(); err != nil {
		return d.rollback(err)
	}
	// Durable. Update memory only now.
	d.size += int64(len(frame))
	d.nextTxn++
	d.applyAt(ops, frameStart, frame)
	d.opsSinceCkpt += len(ops)
	d.bytesSinceCkpt += int64(len(frame))
	d.maybeCheckpoint()
	d.compactIfNeeded()
	return nil
}

// maybeCheckpoint writes a checkpoint if thresholds are exceeded.
// Caller must hold the write lock. Errors are non-fatal.
func (d *DB) maybeCheckpoint() {
	if d.bytesSinceCkpt >= ckptEveryBytes || d.opsSinceCkpt >= ckptEveryOps {
		_ = d.writeCheckpoint()
	}
}

// writeCheckpoint encodes the current index as a checkpoint frame and appends
// it to the file. Caller must hold the write lock.
func (d *DB) writeCheckpoint() error {
	entries := make([]CheckpointEntry, 0, len(d.index))
	for k, e := range d.index {
		entries = append(entries, CheckpointEntry{
			Key:  []byte(k),
			Off:  e.off,
			Vlen: e.vlen,
		})
	}
	frame := EncodeCheckpoint(d.nextTxn, entries)
	if _, err := d.f.WriteAt(frame, d.size); err != nil {
		return err
	}
	if err := d.f.Sync(); err != nil {
		// Torn checkpoint: truncate it away so recovery never sees a partial one.
		_ = d.f.Truncate(d.size)
		return err
	}
	d.lastCkptOff = d.size
	d.size += int64(len(frame))
	d.nextTxn++
	d.bytesSinceCkpt = 0
	d.opsSinceCkpt = 0
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

// Get reads the value from disk using the stored file offset.
// Returns (value, true, nil) on hit, (nil, false, nil) on miss.
func (d *DB) Get(key []byte) ([]byte, bool, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()
	if d.closed {
		return nil, false, ErrClosed
	}
	e, ok := d.index[string(key)]
	if !ok {
		return nil, false, nil
	}
	buf := make([]byte, e.vlen)
	if _, err := d.f.ReadAt(buf, e.off); err != nil {
		return nil, false, err
	}
	return buf, true, nil
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

// deadBytes returns how many bytes in the file belong to overwritten or
// deleted values — i.e. bytes that Compact() would reclaim.
func (d *DB) deadBytes() int64 {
	dead := d.size - int64(headerSize) - d.liveBytes
	if dead < 0 {
		return 0
	}
	return dead
}

// compactIfNeeded triggers Compact when dead bytes exceed 50% of the file.
// Called inside Batch while the write lock is already held — Compact must
// NOT re-acquire it, so we call the internal compactLocked directly.
func (d *DB) compactIfNeeded() {
	if d.size > int64(headerSize)*2 && d.deadBytes() > d.size/2 {
		_ = d.compactLocked() // best-effort; errors are non-fatal
	}
}

// Compact rewrites the database to contain only live keys.
// Safe to call concurrently with reads; acquires the write lock internally.
func (d *DB) Compact() error {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.closed {
		return ErrClosed
	}
	if d.failed {
		return ErrFailed
	}
	return d.compactLocked()
}

// compactLocked does the real work. Caller must hold the write lock.
func (d *DB) compactLocked() error {
	tmp := tmpPath(d.path)

	// Req 5: estimate size of the compacted file and check headroom.
	// compactedSize = header + one frame per live key.
	var compactedSize int64 = int64(headerSize)
	for k, e := range d.index {
		compactedSize += int64(frameHeaderSize + bodyFixedSize + 1 + 2 + 4 + len(k) + int(e.vlen))
	}
	if d.maxBytes > 0 && compactedSize > d.maxBytes {
		return ErrDiskFull
	}

	// ── CP1: before temp file exists ─────────────────────────────────────────
	tf, err := os.OpenFile(tmp, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return fmt.Errorf("kvdb compact: create temp: %w", err)
	}

	// ── CP2: temp file exists, empty ─────────────────────────────────────────
	if _, err := tf.Write(makeHeader()); err != nil {
		tf.Close()
		os.Remove(tmp)
		return fmt.Errorf("kvdb compact: write header: %w", err)
	}

	// ── CP3: temp file has header only ───────────────────────────────────────
	// Write one frame per live key, reading values from the old file.
	newIndex := make(map[string]entry, len(d.index))
	var newSize int64 = int64(headerSize)
	var newLive int64

	for k, e := range d.index {
		val := make([]byte, e.vlen)
		if _, err := d.f.ReadAt(val, e.off); err != nil {
			tf.Close()
			os.Remove(tmp)
			return fmt.Errorf("kvdb compact: read value: %w", err)
		}
		op := Op{Type: OpPut, Key: []byte(k), Value: val}
		frame := EncodeFrame(d.nextTxn, []Op{op})
		if _, err := tf.Write(frame); err != nil {
			tf.Close()
			os.Remove(tmp)
			return fmt.Errorf("kvdb compact: write frame: %w", err)
		}
		// Compute new offset by decoding the frame we just built.
		_, decoded, _, _ := DecodeFrame(frame)
		if len(decoded) == 1 {
			newIndex[k] = entry{
				off:  newSize + int64(decoded[0].ValOff),
				vlen: e.vlen,
			}
		}
		newSize += int64(len(frame))
		newLive += int64(e.vlen)
		d.nextTxn++
	}

	// ── CP4: temp file has all frames, not yet fsynced ────────────────────────
	if err := tf.Sync(); err != nil {
		tf.Close()
		os.Remove(tmp)
		return fmt.Errorf("kvdb compact: fsync temp: %w", err)
	}

	// ── CP5: temp file fsynced, rename not yet done ───────────────────────────
	if err := os.Rename(tmp, d.path); err != nil {
		tf.Close()
		os.Remove(tmp)
		return fmt.Errorf("kvdb compact: rename: %w", err)
	}

	// ── CP6: rename done, dir not yet fsynced ─────────────────────────────────
	_ = syncDir(filepath.Dir(d.path)) // best-effort on Windows

	// ── CP7: fully durable — swap file handle and rebuild index ───────────────
	d.f.Close()
	d.f = tf
	d.size = newSize
	d.index = newIndex
	d.liveBytes = newLive
	return nil
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