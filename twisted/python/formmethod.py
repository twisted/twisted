

"""
Form-based method objects.

This module contains support for descriptive method signatures that can be used
to format methods.  Currently this is only used by woven.

"""

class Argument:
    defaultDefault = None
    def __init__(self, name, default=None, error=None):
        self.name = name
        if default is None:
            default = self.defaultDefault
        self.default = default
        self.error = error

    def addHint(self, hint):
        self.hints.append(hint)
        hint.added(self)

class String(Argument):
    """A single string.
    """

class Integer(Argument):
    """A single integer.
    """

class Choice(Argument):
    """The result of a choice between enumerated types.
    """
    def __init__(self, name, choices=[], default=None, *hints):
        self.choices = choices
        Argument.__init__(self, name, default, *hints)

class FlagSet(Argument):
    """The result of a checkbox group or multi-menu.
    """
    def __init__(self, name, flags=[], default=[], *hints):
        self.flags = flags
        Argument.__init__(self, name, default, *hints)

class Boolean(Argument):
    pass

class PresentationHint:
    """
    A hint to a particular system.
    """


class MethodSignature:

    def __init__(self, *sigList):
        """
        """
        self.methodSignature = sigList

    def addHintTo(self, **kw):
        for k,v in kw.items():
            for a in self.methodSignature:
                if a.name == k:
                    a.name == k
                    a.addHint(v)
                    continue

    def getArgument(self, name):
        for a in self.methodSignature:
            if a.name == name:
                return a

    def method(self, callable):
        return SignedMethod(self, callable)


class SignedMethod:
    """A callable object with a signature.
    """
    def __init__(self, signature, callable):
        self.signature = signature
        self.callable = callable


def test():
    def funky(title, checkone, checktwo, checkn, mnu, desc):
        pass
    msf = MethodSignature(String("title"),
                          Boolean("checkone"),
                          Boolean("checktwo"),
                          FlagSet("checkn", ["zero", "Count Zero",
                                             "one", "Count One",
                                             "two", "Count Two"],
                                  ["one"],
                                  # WebCheckGroup(style="color: orange"),
                                  # GtkCheckGroup(border="3")
                                  ),
                          Choice("mnu",
                                 [['IDENTIFIER', 'Some Innocuous String'],
                                  ['TEST_FORM', 'Just another silly string.'],
                                  ['CONEHEADS', 'Hoo ha.']],
                                 # WebMenu()
                                 ))
    m = msf.method(funky)

    
if __name__ == '__main__':
    test()
