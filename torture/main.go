package main

import (
    "fmt"
    "os"
    "runtime"
)

func main() {
    fmt.Println("KILL IT AND PROVE IT")
    fmt.Println("--------------------")

    fmt.Println("Operating System:", runtime.GOOS)
    fmt.Println("Architecture:", runtime.GOARCH)
    fmt.Println("Process ID:", os.Getpid())
}