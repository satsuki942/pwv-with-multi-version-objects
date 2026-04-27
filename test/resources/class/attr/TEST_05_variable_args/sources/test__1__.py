class Test:

    def a(self, n):
        print(n)

    def b(self, n):
        print(n)

    def c(self, *args):
        print(args[0])

    def d(self, **kwargs):
        print(kwargs['n'])

    def stable_method(self):
        return
