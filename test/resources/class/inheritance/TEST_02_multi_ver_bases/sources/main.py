# 継承元と継承先の両方が複数 version の場合に class 統合後も method を呼べることを検証する。
from student import Student
def main():
    alice = Student("Alice", 67890, "Mathematics")
    bob = Student("Bob", 12345, "Computer Science")
    alice.introduce()
    bob.self_introduce()

if __name__ == "__main__":
    main()
