
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
