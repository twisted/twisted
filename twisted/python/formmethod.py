

"""
Form-based method objects.

This module contains support for descriptive method signatures that can be used
to format methods.  Currently this is only used by woven.

"""

class InputError(Exception):
    """
    An error occurred with some input.
    """

class Argument:
    defaultDefault = None
    def __init__(self, name, default=None, shortDesc=None, longDesc=None, hints=()):
        self.name = name
        if default is None:
            default = self.defaultDefault
        self.default = default
        self.shortDesc = shortDesc
        self.longDesc = longDesc

    def addHint(self, hint):
        self.hints.append(hint)
        hint.added(self)

    def getShortDescription(self):
        return self.shortDesc or self.name.capitalize()

    def getLongDescription(self):
        return self.longDesc or "The %s." % self.name

class String(Argument):
    """A single string.
    """
    defaultDefault = ''

    def coerce(self, val):
        return str(val)

class Text(String):
    """A long string.
    """

class Integer(Argument):
    """A single integer.
    """
    defaultDefault = 0
    def coerce(self, val):
        return int(val)

class Float(Argument):
    def coerce(self, val):
        return float(val)

class Choice(Argument):
    """The result of a choice between enumerated types.
    """
    def __init__(self, name, choices=[], default=None, shortDesc=None, longDesc=None, hints=()):
        self.choices = choices
        Argument.__init__(self, name, default, shortDesc, longDesc, hints)

    def coerce(self, inIdent):
        for ident, val, desc in self.choices:
            if ident == inIdent:
                return val
        else:
            raise InputError("Invalid Choice: %s" % inIdent)


class Flags(Argument):
    """The result of a checkbox group or multi-menu.
    """
    def __init__(self, name, flags=(), default=(), shortDesc=None, longDesc=None, hints=()):
        self.flags = flags
        Argument.__init__(self, name, default, shortDesc, longDesc, hints)

    def coerce(self, inFlagKeys):
        outFlags = []
        for inFlagKey in inFlagKeys:
            for flagKey, flagVal, flagDesc in self.flags:
                if inFlagKey == flagKey:
                    outFlags.append(flagVal)
            else:
                raise InputError("Invalid Flag: %s" % inFlagKey)
        return outFlags


class CheckGroup(Flags):
    pass

class RadioGroup(Choice):
    pass

class Boolean(Argument):
    def coerce(self, inVal):
        if not inVal:
            return 0
        lInVal = str(inVal).lower()
        if lInVal in ('no', 'n', 'f', 'false'):
            return 0
        return 1


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
        return FormMethod(self, callable)


class FormMethod:
    """A callable object with a signature.
    """
    def __init__(self, signature, callable):
        self.signature = signature
        self.callable = callable

    def getArgs(self):
        return tuple(self.signature.methodSignature)

    def call(self,*args,**kw):
        return self.callable(*args,**kw)


def test():
    def funky(title, checkone, checktwo, checkn, mnu, desc):
        pass
    msf = MethodSignature(String("title"),
                          Boolean("checkone"),
                          Boolean("checktwo"),
                          Flags("checkn", ["zero", 0, "Count Zero",
                                           "one", 1, "Count One",
                                           "two", 2, "Count Two"],
                                ["one"],
                                # hints=[WebCheckGroup(style="color: orange"),
                                # GtkCheckGroup(border="3")]
                                  ),
                          Choice("mnu",
                                 [['IDENTIFIER', 'Sphere', 'Some Innocuous String'],
                                  ['TEST_FORM', 'Cube', 'Just another silly string.'],
                                  ['CONEHEADS', 'Cone', 'Hoo ha.']],
                                 # hints=[WebMenu()]
                                 ))
    m = msf.method(funky)

    
if __name__ == '__main__':
    test()
