"""
Test cases for todo
"""


from pyunit import unittest

from twisted.pim import todo

class TodoTestCase(unittest.TestCase):
    def setUp(self):
        self.todo = todo.TodoItem("me", "you", "a bug", "fix it")

    def testTodo(self):
        self.initialCheck()
        self.update()
        self.secondCheck()

    def initialCheck(self):
        assert self.todo.getItem() == ("me", "you", "a bug", "fix it"), "Attributes gotten with accessor weren't what I expected."

    def update(self):
        self.todo.updateItem("you", "me", "a buglet", "fix it, please")

    def secondCheck(self):
        assert self.todo.getItem() == ("you", "me", "a buglet", "fix it, please"), "Attributes gotten with access weren't what I expected."

testCases = [TodoTestCase]
