"""Regexs for Banana"""


class _Special:

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

START = _Special('START')
END = _Special('END')

class _Final:

    def __init__(self, name, nullable):
        self.name = name
        self.nullable = lambda: nullable

    def __call__(self, token):
        return failure
    
    def __repr__(self):
        return self.name

failure = _Final("failure", 0)
null = _Final("null", 1)

class Pattern:
    
    def __init__(self, *args):
        self.args = args


class _After(Pattern):

    def nullable(self):
        for i in self.args:
            if not callable(i) or not i.nullable():
                return 0
        return 1

    def __repr__(self):
        return "After%s" % (self.args,)
    
    def __call__(self, token):
        pattern = self.args[0]
        if callable(pattern):
            result = pattern(token)
            if result == null:
                return After(*self.args[1:])
            elif result == failure:
                return failure
            elif result.nullable():
                return Either(After(result, *self.args[1:]), After(*self.args[1:]))
            else:
                return After(result, *self.args[1:])
        elif pattern == token:
            return After(*self.args[1:])
        else:
            return failure

def After(*args):
    if failure in args:
        return failure
    elif not args:
        return null
    elif len(args) == 1:
        return args[0]
    else:
        return _After(*args)


class _Either(Pattern):

    def __repr__(self):
        return "Either%s" % (self.args,)

    def nullable(self):
        for i in self.args:
            if callable(i) and i.nullable():
                return 1
        return 0
        
    def __call__(self, token):
        alternatives = []
        for pattern in self.args:
            if callable(pattern):
                result = pattern(token)
                if result != failure:
                    alternatives.append(result)
            elif pattern == token:
                alternatives.append(null)
        if alternatives:
            return Either(*alternatives)
        else:
            return failure

def Either(*args):
    if not args:
        return null
    elif len(args) == 1:
        return args[0]
    else:
        return _Either(*args)


class AtomType:

    def nullable(self):
        return 0

    def __repr__(self):
        return "Atom(%s)" % self.klass.__name__
    
    def __init__(self, klass):
        self.klass = klass

    def __call__(self, token):
        if isinstance(token, self.klass):
            return null
        else:
            return failure

integer = AtomType(int)
string = AtomType(str)


def Sequence(*contents):
    return After(START, *contents + (END,))


class OneOrMore:

    def __init__(self, pattern):
        self.pattern = pattern
        
    def nullable(self):
        return self.pattern.nullable()

    def __repr__(self):
        return "OneOrMore(%s)" % (self.pattern,)

    def __call__(self, token):
        result = self.pattern(token)
        if result == null:
            return Either(null, self)
        elif result == failure:
            return failure
        else:
            return Either(result, After(result, self))

def match(pattern, iterator):
    print pattern
    for i in iterator:
        pattern = pattern(i)
        print repr(i).ljust(7), "-->",  pattern
        if pattern == failure:
            break
    print "Matched?", pattern.nullable()

match(Sequence("dict", OneOrMore(After(integer, integer))), [START, "dict", 12, 2, 2, 4, END])
