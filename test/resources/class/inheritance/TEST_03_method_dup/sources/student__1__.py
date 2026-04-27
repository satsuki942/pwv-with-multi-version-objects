from member import Member

class Student(Member):

    def __init__(self, name, id):
        super().__init__(name, id)
