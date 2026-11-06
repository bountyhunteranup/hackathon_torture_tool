import time
import urllib.error
import urllib.request


class RecoveryManager:

    def __init__(self, controller, database_url):
        self.controller = controller
        self.database_url = database_url

    def wait_until_ready(self, timeout=10):
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:

            if not self.controller.is_running():
                raise RuntimeError("Database process exited unexpectedly")

            try:
                request = urllib.request.Request(
                    self.database_url + "/__health_check__",
                    method="GET"
                )

                urllib.request.urlopen(request, timeout=1)

                return True

            except urllib.error.HTTPError as error:
                # A 404 means the HTTP server responded.
                if error.code == 404:
                    return True
                raise

            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.2)

        raise TimeoutError("Database did not become ready")

    def restart(self):
        print("Restarting database...")

        self.controller.start()
        self.wait_until_ready()

        print("Database is ready again!")