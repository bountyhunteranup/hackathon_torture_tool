package engine

import (
	"encoding/binary"
	"errors"
	"io"
)

const (
	typePut    byte = 0x01
	typeDelete byte = 0x02
	headerSize      = 9 // 1 + 4 + 4
)

type frame struct {
	typ    byte
	key    []byte
	value  []byte
}

func encodeFrame(w io.Writer, f frame) error {
	kl := uint32(len(f.key))
	vl := uint32(len(f.value))
	hdr := [headerSize]byte{}
	hdr[0] = f.typ
	binary.BigEndian.PutUint32(hdr[1:5], kl)
	binary.BigEndian.PutUint32(hdr[5:9], vl)
	if _, err := w.Write(hdr[:]); err != nil {
		return err
	}
	if _, err := w.Write(f.key); err != nil {
		return err
	}
	_, err := w.Write(f.value)
	return err
}

func decodeFrame(r io.Reader) (frame, error) {
	var hdr [headerSize]byte
	if _, err := io.ReadFull(r, hdr[:]); err != nil {
		return frame{}, err
	}
	typ := hdr[0]
	if typ != typePut && typ != typeDelete {
		return frame{}, errors.New("unknown frame type")
	}
	kl := binary.BigEndian.Uint32(hdr[1:5])
	vl := binary.BigEndian.Uint32(hdr[5:9])
	key := make([]byte, kl)
	val := make([]byte, vl)
	if _, err := io.ReadFull(r, key); err != nil {
		return frame{}, err
	}
	if _, err := io.ReadFull(r, val); err != nil {
		return frame{}, err
	}
	return frame{typ: typ, key: key, value: val}, nil
}
