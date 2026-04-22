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
