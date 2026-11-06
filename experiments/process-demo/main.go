
package main

import (
    "fmt"
    "os/exec"
    "time"
)

func main() {

    // 1. Prepare a child process
    cmd := exec.Command("/bin/sleep", "30")

    // 2. Start the child process
    err := cmd.Start()

    if err != nil {
        fmt.Println("Failed to start:", err)
        return
    }

    // 3. Obtain its process ID
    fmt.Println("Child process started!")
    fmt.Println("PID:", cmd.Process.Pid)

    // 4. Let it run for two seconds
    time.Sleep(2 * time.Second)

    // 5. Terminate the child process
    fmt.Println("Killing child process...")

    err = cmd.Process.Kill()

    if err != nil {
        fmt.Println("Kill failed:", err)
        return
    }

    // 6. Wait for the process to exit
    err = cmd.Wait()

    fmt.Println("Child process terminated.")

    if err != nil {
        fmt.Println("Exit information:", err)
    }
}
