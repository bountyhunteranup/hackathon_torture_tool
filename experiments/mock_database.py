
import time
import os

print("MOCK DATABASE STARTED", flush=True)
print("Database PID:", os.getpid(), flush=True)

while True:
    time.sleep(1)
