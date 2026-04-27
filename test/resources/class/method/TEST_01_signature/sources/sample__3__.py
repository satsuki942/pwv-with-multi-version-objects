class Runner:
    def call(self, x, *, mode):
        return f"kwonly:{x}:{mode}"
