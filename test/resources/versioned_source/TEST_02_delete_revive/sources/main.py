class A:
    def __init__(self, value):
        self.value = value

    def label(self):
        return f"v1:{self.value}"

with _mv.v(2).delete():
    del A

with _mv.v(4).revive():
    class A:
        def __init__(self, value, suffix):
            self.value = value
            self.suffix = suffix

        def label(self):
            return f"v4:{self.value}{self.suffix}"

print(A("x").label())
print(A("y", "!").label())
