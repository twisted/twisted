
# this is the closest I've come to coding in a fever dream - glyph

### FOR BONUS POINTS, RUN THIS, READ THE BOTTOM OF THE FILE, AND TRY TO FIGURE
### OUT HOW I DID IT

class EachCall:
    def __init__(self, name, args, kw):
        self.name = name
        self.args = args
        self.kw = kw

    def __call__(self, one):
        return getattr(one, self.name)(*self.args,**self.kw)

class EachMap:
    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kw):
        return EachCall(self.name, args, kw)

class Each:
    def __coerce__(self, other):
        return None
    def __getattr__(self, name):
        return EachMap(name)

each = Each()

class A:
    num = 0
    def foo(self):
        A.num += 1
        return A.num

#### BONUS: READ BELOW

print map(each + 1, [1, 2, 3])
