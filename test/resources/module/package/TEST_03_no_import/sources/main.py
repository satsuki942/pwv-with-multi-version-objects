# import されない通常 class と versioned class が同一 entrypoint 内で共存できることを検証する。
from cat import Cat

def main():
    Dog('Pochi').speak()
    cat = Cat('Tama')
    cat.speak()
    cat.introduce()

class Dog:

    def __init__(self, name):
        self.name = name

    def speak(self):
        print('Woof!')
if __name__ == '__main__':
    main()
