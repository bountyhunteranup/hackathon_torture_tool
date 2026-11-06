package engine

import (
	"bytes"
	"testing"
)

func sampleOps() []Op {
	return []Op{
		{Type: OpPut, Key: []byte("a"), Value: []byte("1")},
		{Type: OpDel, Key: []byte("b")},
		{Type: OpPut, Key: []byte("c"), Value: []byte("three")},
	}
}

func TestRoundTrip(t *testing.T) {
	frame := EncodeFrame(42, sampleOps())
	txn, ops, n, err := DecodeFrame(frame)
	if err != nil || txn != 42 || n != len(frame) || len(ops) != 3 {
		t.Fatalf("bad decode: txn=%d n=%d ops=%d err=%v", txn, n, len(ops), err)
	}
	for i, want := range sampleOps() {
		if ops[i].Type != want.Type || !bytes.Equal(ops[i].Key, want.Key) ||
			!bytes.Equal(ops[i].Value, want.Value) {
			t.Fatalf("op %d mismatch: %+v", i, ops[i])
		}
	}
}

// Torn write: a frame cut at ANY length must be rejected.
func TestTornWriteEveryLength(t *testing.T) {
	frame := EncodeFrame(1, sampleOps())
	for cut := 0; cut < len(frame); cut++ {
		if _, _, _, err := DecodeFrame(frame[:cut]); err != ErrIncomplete {
			t.Fatalf("cut at %d/%d: want ErrIncomplete, got %v", cut, len(frame), err)
		}
	}
}

// Any single flipped byte must be rejected.
func TestCorruptionEveryByte(t *testing.T) {
	frame := EncodeFrame(1, sampleOps())
	for i := range frame {
		bad := append([]byte(nil), frame...)
		bad[i] ^= 0xFF
		if _, _, _, err := DecodeFrame(bad); err != ErrIncomplete {
			t.Fatalf("flip at byte %d accepted (err=%v)", i, err)
		}
	}
}

func TestEdgeCases(t *testing.T) {
	cases := map[string][]Op{
		"empty value": {{Type: OpPut, Key: []byte("k"), Value: nil}},
		"1MB value":   {{Type: OpPut, Key: []byte("k"), Value: bytes.Repeat([]byte{7}, 1<<20)}},
		"1024B key":   {{Type: OpPut, Key: bytes.Repeat([]byte{'k'}, 1024), Value: []byte("v")}},
		"zero ops":    {},
	}
	for name, ops := range cases {
		frame := EncodeFrame(9, ops)
		_, got, n, err := DecodeFrame(frame)
		if err != nil || n != len(frame) || len(got) != len(ops) {
			t.Fatalf("%s: err=%v n=%d/%d ops=%d/%d", name, err, n, len(frame), len(got), len(ops))
		}
		for i := range ops {
			if !bytes.Equal(got[i].Key, ops[i].Key) || !bytes.Equal(got[i].Value, ops[i].Value) {
				t.Fatalf("%s: op %d differs", name, i)
			}
		}
	}
}

// Two frames back to back decode one after the other, using n as the offset.
func TestSequentialFrames(t *testing.T) {
	a := EncodeFrame(1, sampleOps())
	b := EncodeFrame(2, sampleOps()[:1])
	data := append(append([]byte(nil), a...), b...)
	_, _, n1, err := DecodeFrame(data)
	if err != nil || n1 != len(a) {
		t.Fatalf("first frame: n=%d err=%v", n1, err)
	}
	txn, _, n2, err := DecodeFrame(data[n1:])
	if err != nil || txn != 2 || n2 != len(b) {
		t.Fatalf("second frame: txn=%d n=%d err=%v", txn, n2, err)
	}
}