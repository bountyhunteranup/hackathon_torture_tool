"""CRUD smoke test for the current line-protocol DatabaseClient."""

from torture.environment import TestEnvironment


def main():
    with TestEnvironment() as environment:
        database = environment.database

        print("--- PUT ---")
        assert database.put("balance", "500") == 204

        print("\n--- GET ---")
        assert database.get("balance") == "500"

        print("\n--- DELETE ---")
        assert database.delete("balance") == 204

        print("\n--- VERIFY DELETE ---")
        assert database.get("balance") is None

    print("\nCLIENT TEST PASSED!")


if __name__ == "__main__":
    main()
