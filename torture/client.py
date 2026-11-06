import json
import urllib.error
import urllib.parse
import urllib.request


class DatabaseClient:
    def dump(self):
        url = f"{self.base_url}/admin/dump"

        request = urllib.request.Request(
            url,
            method="GET"
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)

    def __init__(self, base_url="http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip("/")

    def put(self, key, value):
        url = self._url(key)

        data = json.dumps({"Value": value}).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT"
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status

    def get(self, key):
        url = self._url(key)

        request = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.read().decode("utf-8")

        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

    def delete(self, key):
        url = self._url(key)

        request = urllib.request.Request(url, method="DELETE")

        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status

    def _url(self, key):
        encoded_key = urllib.parse.quote(key, safe="")
        return f"{self.base_url}/{encoded_key}"