class nil:
    def __init__(self):
        self.car = self
        self.cdr = self
    def __nonzero__(self):
        return 0
nil = nil()

class cons:
    def __init__(self, car,cdr):
        self.car = car
        self.cdr = cdr

    def __iter__(self):
        return ConsIterator(self)

    def __repr__(self):
        return "[%s . %s]" % (self.car, self.cdr)

    def __eq__(self, obj):
        if not isinstance(obj, cons):
            return 0
        if (self.car == obj.car) and (self.cdr == obj.cdr):
            return 1

    __str__ = __repr__

class ConsIterator:
    def __init__(self, cons):
        self.current = cons
    def next(self):
        c = self.current
        if c != nil:            
            self.current = c.cdr        
            return c
        else:
            raise StopIteration

def list(*exp):
    head = lispList = cons(nil, nil)
    for val in exp:
        newLispList = cons(nil, nil)
        lispList.car = val
        lispList.cdr = newLispList
        oldCons = lispList
        lispList = newLispList
    oldCons.cdr= nil
    return head
     
