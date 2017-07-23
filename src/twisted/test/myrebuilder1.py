
class A:
    def a(self):
        return 'a'
try:
    object
except NameError:
    pass
else:
    class B(A, object):
        def b(self):
            return 'b'
class Inherit(A):
    def a(self):
        return 'c'
