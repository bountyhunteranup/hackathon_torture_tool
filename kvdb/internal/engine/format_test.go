package engine

import (
	"bytes"
	"testing"
)

func TestRoundTrip(t *testing.T) {
	cases := []frame{
		{typ: typePut, key: []byte("hello"), value: []byte("world")},
		{typ: typeDelete, key: []byte("gone"), value: nil},
	}
	for _, c := range cases {
		var buf bytes.Buffer
		if err := encodeFrame(&buf, c); err != nil {
			t.Fatal(err)
		}
		got, err := decodeFrame(&buf)
		if err != nil {
			t.Fatal(err)
		}
		if got.typ != c.typ || string(got.key) != string(c.key) || string(got.value) != string(c.value) {
			t.Fatalf("mismatch: got %+v want %+v", got, c)
		}
	}
}
