package engine

import (
	"bytes"
	"os"
)

// CheckFile validates the header and counts valid frames without modifying
// the file. tail is the number of trailing bytes that are not a valid frame
// (a torn write that Open would truncate).
func CheckFile(path string) (frames int, tail int, err error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, 0, err
	}
	hdr := makeHeader()
	if len(data) < headerSize {
		if bytes.HasPrefix(hdr, data) {
			return 0, len(data), nil
		}
		return 0, 0, ErrNotOurFile
	}
	if !bytes.Equal(data[:headerSize], hdr) {
		return 0, 0, ErrNotOurFile
	}
	off := headerSize
	for off < len(data) {
		_, _, n, derr := DecodeFrame(data[off:])
		if derr != nil {
			break
		}
		frames++
		off += n
	}
	return frames, len(data) - off, nil
}