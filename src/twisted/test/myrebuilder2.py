
class A:
    def a(self):
        return 'b'
try:
    object
except NameError:
    pass
else:
    class B(A, object):
        def b(self):
            return 'c'

class Inherit(A):
    def a(self):
        return 'd'
