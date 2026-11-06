.PHONY: all clean test

all:
	go build -o kvdb ./cmd/kvdb
	go build -o torture ./cmd/torture

test:
	go test ./...

clean:
	rm -f kvdb torture torture.db
