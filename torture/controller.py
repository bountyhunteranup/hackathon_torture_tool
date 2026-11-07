
import os
import subprocess


class ProcessController:

    def __init__(self, command, extra_env=None):
        self.command = command
        self.process = None
        self.extra_env = extra_env or {}

    def start(self):

        if self.is_running():
            raise RuntimeError("Process is already running")

        process_env = os.environ.copy()
        process_env.update(self.extra_env)

        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=process_env
        )

        print("Database started. PID:", self.process.pid)

    def is_running(self):
        return (
            self.process is not None
            and self.process.poll() is None
        )

    def stop(self):

        if not self.is_running():
            return

        self.process.stdin.close()

        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

            raise RuntimeError("Database did not stop after stdin closed")

        print("Database stopped. Exit:", self.process.returncode)

    def kill(self):

        if self.is_running():
            self.process.kill()
            self.process.wait(timeout=5)
            print("Database killed.")
