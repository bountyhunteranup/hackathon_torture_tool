"""Exercise overlapping, out-of-order-capable requests against the Go server."""

from concurrent.futures import ThreadPoolExecutor

from torture.environment import TestEnvironment
from torture.concurrent_client import ConcurrentDatabaseClient


with TestEnvironment(client_class=ConcurrentDatabaseClient) as environment:
    client = environment.database
    items = [(f"parallel-{number}", f"value-{number}") for number in range(40)]

    with ThreadPoolExecutor(max_workers=12) as workers:
        list(workers.map(lambda item: client.put(*item), items))
        actual = list(workers.map(lambda item: client.get(item[0]), items))

    expected = [value for _, value in items]
    assert actual == expected

    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(client.delete, [key for key, _ in items]))

    assert client.dump() == {}
    print("CONCURRENT CLIENT TEST PASSED (40 puts, 40 gets, 40 deletes)")
