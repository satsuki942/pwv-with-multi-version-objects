import math

with _mv.v(2).imports():
    import sys

x = _mv.var(1, variable_versioning="generated")

with _mv.v(2).change():
    x = 2

def f(value):
    return f"v1:{value}"

with _mv.v(2).rename("g"):
    def g(value, suffix=""):
        return f"v2:{value}{suffix}"

class A:
    def __init__(self, value):
        self.value = value

    def label(self):
        return f"v1:{self.value}"

with _mv.v(2).change():
    class A:
        def __init__(self, value, suffix=""):
            self.value = value
            self.suffix = suffix

        def label(self):
            return f"v2:{self.value}{self.suffix}"

    def _sync_from_v1_to_v2(obj):
        obj.suffix = ""

print(x)
print(f("a"))
print(g("b", "!"))
print(A("c", "?").label())
