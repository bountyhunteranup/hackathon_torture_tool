package engine

import (
	"errors"
	"io"
	"os"
	"sync"
)

var ErrNotFound = errors.New("key not found")

type DB struct {
	mu    sync.RWMutex
	file  *os.File
	index map[string][]byte // key → latest value (nil = deleted)
}

func Open(path string) (*DB, error) {
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE, 0644)
	if err != nil {
		return nil, err
	}
	db := &DB{file: f, index: make(map[string][]byte)}
	if err := db.load(); err != nil {
		f.Close()
		return nil, err
	}
	return db, nil
}

func (db *DB) load() error {
	if _, err := db.file.Seek(0, io.SeekStart); err != nil {
		return err
	}
	for {
		fr, err := decodeFrame(db.file)
		if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
			break
		}
		if err != nil {
			return err
		}
		if fr.typ == typeDelete {
			delete(db.index, string(fr.key))
		} else {
			db.index[string(fr.key)] = fr.value
		}
	}
	return nil
}

func (db *DB) Put(key, value string) error {
	db.mu.Lock()
	defer db.mu.Unlock()
	if _, err := db.file.Seek(0, io.SeekEnd); err != nil {
		return err
	}
	if err := encodeFrame(db.file, frame{typ: typePut, key: []byte(key), value: []byte(value)}); err != nil {
		return err
	}
	db.index[key] = []byte(value)
	return nil
}

func (db *DB) Get(key string) (string, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()
	v, ok := db.index[key]
	if !ok {
		return "", ErrNotFound
	}
	return string(v), nil
}

func (db *DB) Delete(key string) error {
	db.mu.Lock()
	defer db.mu.Unlock()
	if _, err := db.file.Seek(0, io.SeekEnd); err != nil {
		return err
	}
	if err := encodeFrame(db.file, frame{typ: typeDelete, key: []byte(key)}); err != nil {
		return err
	}
	delete(db.index, key)
	return nil
}

type BatchOp struct {
	Delete bool
	Key    string
	Value  string
}

func (db *DB) Batch(ops []BatchOp) error {
	db.mu.Lock()
	defer db.mu.Unlock()
	if _, err := db.file.Seek(0, io.SeekEnd); err != nil {
		return err
	}
	for _, op := range ops {
		var fr frame
		if op.Delete {
			fr = frame{typ: typeDelete, key: []byte(op.Key)}
		} else {
			fr = frame{typ: typePut, key: []byte(op.Key), value: []byte(op.Value)}
		}
		if err := encodeFrame(db.file, fr); err != nil {
			return err
		}
	}
	for _, op := range ops {
		if op.Delete {
			delete(db.index, op.Key)
		} else {
			db.index[op.Key] = []byte(op.Value)
		}
	}
	return nil
}

func (db *DB) Dump() map[string]string {
	db.mu.RLock()
	defer db.mu.RUnlock()
	out := make(map[string]string, len(db.index))
	for k, v := range db.index {
		out[k] = string(v)
	}
	return out
}

func (db *DB) Check() error {
	db.mu.RLock()
	defer db.mu.RUnlock()
	if _, err := db.file.Seek(0, io.SeekStart); err != nil {
		return err
	}
	for {
		_, err := decodeFrame(db.file)
		if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
			break
		}
		if err != nil {
			return err
		}
	}
	return nil
}

func (db *DB) Close() error {
	return db.file.Close()
}
