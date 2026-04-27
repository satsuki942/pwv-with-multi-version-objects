from member import Member

class Student(Member):

    def __init__(self, name, id, major):
        super().__init__(name, id)
        self.major = major

    def self_introduce(self):
        print(f'Hi, My name is {self.get_name()}.')
