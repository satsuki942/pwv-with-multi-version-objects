class A:

    def __init__(self):
        self.a = 1

    def method(self):
        print(self.a)

        def inner_method():
            self = 2
            print(self)
        inner_method()
        print(self.a)
