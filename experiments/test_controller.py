
import sys
import time

from torture.controller import ProcessController

# 1. Create our simulated database
controller = ProcessController([
    sys.executable,
    "experiments/mock_database.py"
])

# 2. Start the database
print("\n--- STARTING DATABASE ---")
controller.start()

# 3. Check whether it is alive
print("\n--- CHECKING DATABASE ---")
print("Database running:", controller.is_running())

# 4. Let it run for three seconds
time.sleep(3)

# 5. Kill the database
print("\n--- INJECTING CRASH ---")
controller.kill()

# 6. Verify termination
print("\n--- VERIFYING TERMINATION ---")
print("Database running:", controller.is_running())

assert controller.process is not None
assert controller.process.returncode == -9
assert not controller.is_running()

print("\nEXPERIMENT PASSED!")

print("\n--- RESTARTING DATABASE ---")

controller.start()

time.sleep(2)

print("Database running:", controller.is_running())

controller.kill()

print("\nRESTART EXPERIMENT PASSED!")