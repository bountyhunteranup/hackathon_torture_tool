class Oracle:

    def __init__(self):
        self.expected_state = {}
        self.known_keys = set()

    def put(self, key, value):
        self.expected_state[key] = value
        self.known_keys.add(key)

    def get(self, key):
        return self.expected_state.get(key)

    def delete(self, key):
        self.expected_state.pop(key, None)
        self.known_keys.add(key)