
import subprocess
import signal


class ProcessController:

    def __init__(self, command):
        self.command = command
        self.process: subprocess.Popen | None = None

    def start(self):

        if self.is_running():
            raise RuntimeError("Process is already running")

        self.process = subprocess.Popen(self.command)

        print("Process started!")
        print("PID:", self.process.pid)

    def is_running(self):

        process = self.process

        if process is None:
            return False

        return process.poll() is None

    def kill(self):

        process = self.process

        if process is None or process.poll() is not None:
            print("Process is not running")
            return

        print("Sending SIGKILL...")

        process.send_signal(signal.SIGKILL)

        try:
            process.wait(timeout=5)

            print("Process killed!")
            print("Exit code:", process.returncode)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Process did not terminate after SIGKILL")

    def stop(self):

        process = self.process

        if process is None or process.poll() is not None:
            print("Process is not running")
            return

        process.terminate()

        try:
            process.wait(timeout=5)

            print("Process stopped gracefully!")

        except subprocess.TimeoutExpired:
            print("Graceful shutdown timed out")
            self.kill()
