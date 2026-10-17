"""Small evaluation fixture; only Python's standard library is required."""


class Store:
    def __init__(self, initial=None):
        self.rows = dict(initial or {})
        self.active = 0

    def begin(self):
        self.active += 1
        return Transaction(self)


class Transaction:
    def __init__(self, store):
        self.store = store
        self.pending = dict(store.rows)

    def put(self, key, value):
        self.pending[key] = value

    def commit(self):
        self.store.rows = dict(self.pending)

    def close(self):
        self.store.active -= 1


def import_batch(store, rows):
    """All rows become visible together. Always release the transaction.

    begin, put and commit may raise OSError BEFORE producing an effect.
    close is infallible. Any OSError leaves original rows unchanged.
    """
    tx = store.begin()
    try:
        for key, value in rows:
            tx.put(key, value)
        tx.commit()
    finally:
        tx.close()
