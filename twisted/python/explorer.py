
# Twisted Imports
from twisted.python import authenticator

class ObjectBrowser:
    def __init__(self, ns):
        self.ns = ns

    def code(self, code):
        try:
            code = compile(code, '$navigator$', 'eval')
            return eval(code, self.ns.__dict__)
        except SyntaxError:
            code = compile(code, '$navigator$', 'exec')
            exec code in self.ns.__dict__

    def move(self, ns):
        self.ns = ns

    def callMeth(self, meth, *args, **kwargs):
        return apply(getattr(self.ns, meth), args, kwargs)

    def getAttrs(self):
        return dir(self.ns)

class SecureObjectBrowser(ObjectBrowser):
    """I am a secure object browser, which only allows you to move to a
    namespace that's contained in your current namespace."""
    def move(self, ns):
        """This method should check that the new namespace is either in your current
        namespace or your last namespace."""
        #This is easy if I require 'ns' to be a string, but that would break
        #compatibility with ObjectBrowser. And if I made ObjectBrowser.move
        #accept a string, how will I make it any more flexible than SecureObjectBrowser
        #(ie, to allow an arbitrary namespace)
        if ns in dir(self.ns):
            self.ns = getattr(self.ns, ns)

    def code(self, code):
        raise authenticator.Unauthorized("You are not allowed to do that in a Secure Object Browser.")
