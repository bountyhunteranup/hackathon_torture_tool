@echo off
go build -o kvdb.exe ./cmd/kvdb
go build -o torture.exe ./cmd/torture
echo Build complete: kvdb.exe and torture.exe
