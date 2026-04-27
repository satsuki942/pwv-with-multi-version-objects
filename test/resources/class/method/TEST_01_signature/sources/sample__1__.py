class Runner:
    def call(self, **kwargs):
        return f"kwargs:{sorted(kwargs)}"
