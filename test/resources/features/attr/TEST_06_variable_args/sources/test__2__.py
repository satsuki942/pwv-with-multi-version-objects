class Test:

    def a(self, *args):
        print(args[0])

    def b(self, **kwargs):
        print(kwargs['n'])

    def c(self, *args):
        print(args[0])

    def d(self, **kwargs):
        print(kwargs['n'])

    def new_method(self):
        return
