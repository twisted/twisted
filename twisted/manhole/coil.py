from twisted.python import roots
from twisted.web import widgets
from twisted.protocols import protocol

"""Twisted COIL: COnfiguration ILlumination.

An end-user direct-manipulation interface to Twisted, accessible through the
web.
"""

class PortCollection(roots.Homogenous):
    """A collection of Ports; names may only be strings which represent port numbers.
    """
    def __init__(self):
        roots.Homogenous.__init__(self, protocol.Factory)

        # the fact that this accepts protocol.Factories should indicate that
        # there is a menu allowing one to add protocol.Factories to it.
        # (Attributes might be able to be empty (have a None value) and
        # therefore indictate a 'replace' or 'add' option for that menu)
        # are things which can be added always Attributes?  It would make it a
        # heck of a lot easier to generate forms for them if so.

        # So: you must register to be an instantiatable (for config) subclass
        # of protocol.Factory, or any other class specified in one of these
        # type specifiers.  Given that this registry is going to be global in
        # all likelihood, there will be some interaction with rebuild.

    def nameConstraint(self, name):
        """roots.Constrained.nameConstraint
        """
        try:
            portno = int(name)
        except ValueError:
            raise roots.ConstraintViolation("Not a port number: %s" % repr(name))
        else:
            return 1


class Configurator(widgets.Gadget, widgets.StreamWidget):
    """A web configuration interface for Twisted.

    This configures the toplevel application.
    """
    def __init__(self, app):
        widgets.Gadget.__init__(self)
        self.app = app

    def stream(self, request):
        '''
        display a tree with links in it to hit the various nodes
        determine from the session what "main" widget to display?
        '''
