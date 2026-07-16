from contextlib import contextmanager


class Database:
    def __init__(self, path: str):
        self.path = path
        # TODO: 初始化各组件

    def execute(self, sql: str):
        raise NotImplementedError

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@contextmanager
def open(path: str):
    db = Database(path)
    try:
        yield db
    finally:
        db.close()
