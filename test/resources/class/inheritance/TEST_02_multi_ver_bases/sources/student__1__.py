from member import Member

class Student(Member):

    def __init__(self, name, id, major):
        super().__init__(name, id)
        self.major = major

    def introduce(self):
        print(f'Hi, My id is {self.get_id()}.')
