# -*- test-case-name: twisted.test.test_issues -*-

import time

class Commentable:
    def __init__(self, initialCommenter=None, initialComment=None):
        self.comments = []
        if initialComment:
            self.addComment(initialCommenter, initialComment)

    def addComment(self, commenter, commentText):
        self.comments.append((commenter, commentText, time.time()))

