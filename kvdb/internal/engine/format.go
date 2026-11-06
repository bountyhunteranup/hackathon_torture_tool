package engine

import (
	"encoding/binary"
	"errors"
	"hash/crc32"
)

const (
	frameMagic      uint32 = 0x4B564442 // "KVDB"
	OpPut           byte   = 1
	OpDel           byte   = 2
	frameHeaderSize        = 12 // magic(4) + bodyLen(4) + crc(4)
	bodyFixedSize          = 12 // txnID(8) + opCount(4)
)

var ErrIncomplete = errors.New("incomplete or corrupt frame")

var crcTable = crc32.MakeTable(crc32.Castagnoli)

type Op struct {
	Type  byte
	Key   []byte
	Value []byte
}

// Frame: [magic 4][bodyLen 4][crc32c 4][txnID 8][opCount 4][ops...]
// Op:    [type 1][keyLen 2][valLen 4][key][value]
// The CRC covers the whole body (everything after the crc field).
func EncodeFrame(txnID uint64, ops []Op) []byte {
	bodyLen := bodyFixedSize
	for _, op := range ops {
		bodyLen += 1 + 2 + 4 + len(op.Key) + len(op.Value)
	}
	buf := make([]byte, frameHeaderSize+bodyLen)
	binary.LittleEndian.PutUint32(buf[0:], frameMagic)
	binary.LittleEndian.PutUint32(buf[4:], uint32(bodyLen))

	body := buf[frameHeaderSize:]
	binary.LittleEndian.PutUint64(body[0:], txnID)
	binary.LittleEndian.PutUint32(body[8:], uint32(len(ops)))
	p := bodyFixedSize
	for _, op := range ops {
		body[p] = op.Type
		p++
		binary.LittleEndian.PutUint16(body[p:], uint16(len(op.Key)))
		p += 2
		binary.LittleEndian.PutUint32(body[p:], uint32(len(op.Value)))
		p += 4
		p += copy(body[p:], op.Key)
		p += copy(body[p:], op.Value)
	}
	binary.LittleEndian.PutUint32(buf[8:], crc32.Checksum(body, crcTable))
	return buf
}

// DecodeFrame reads one frame from the start of data.
// It returns ErrIncomplete for anything that is not a complete, valid frame.
func DecodeFrame(data []byte) (txnID uint64, ops []Op, n int, err error) {
	if len(data) < frameHeaderSize ||
		binary.LittleEndian.Uint32(data[0:]) != frameMagic {
		return 0, nil, 0, ErrIncomplete
	}
	bodyLen := int(binary.LittleEndian.Uint32(data[4:]))
	if bodyLen < bodyFixedSize || bodyLen > len(data)-frameHeaderSize {
		return 0, nil, 0, ErrIncomplete
	}
	body := data[frameHeaderSize : frameHeaderSize+bodyLen]
	if crc32.Checksum(body, crcTable) != binary.LittleEndian.Uint32(data[8:]) {
		return 0, nil, 0, ErrIncomplete
	}
	txnID = binary.LittleEndian.Uint64(body[0:])
	count := int(binary.LittleEndian.Uint32(body[8:]))
	p := bodyFixedSize
	for i := 0; i < count; i++ {
		if p+7 > len(body) {
			return 0, nil, 0, ErrIncomplete
		}
		op := Op{Type: body[p]}
		kl := int(binary.LittleEndian.Uint16(body[p+1:]))
		vl := int(binary.LittleEndian.Uint32(body[p+3:]))
		p += 7
		if p+kl+vl > len(body) {
			return 0, nil, 0, ErrIncomplete
		}
		op.Key = body[p : p+kl]
		op.Value = body[p+kl : p+kl+vl]
		p += kl + vl
		ops = append(ops, op)
	}
	return txnID, ops, frameHeaderSize + bodyLen, nil
}