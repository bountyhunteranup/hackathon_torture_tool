
import subprocess
import time

# 1. Prepare a child process
process = subprocess.Popen(["/bin/sleep", "30"])
print("Parent PID:", __import__("os").getpid())
print("Child PID:", process.pid)

# 2. Display the process ID
print("Child process started!")
print("Process ID:", process.pid)

# 3. Allow the process to run
time.sleep(5)

# 4. Kill the child process
print("Killing child process...")
print("Before kill:", process.poll())

process.kill()

# 5. Wait for termination
process.wait()
print("After kill:", process.poll())

print("Child process terminated!")
print("Exit code:", process.returncode)
