# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
A plugin for running services given a fully-qualified Python name, like::

  $ twistd run myapp
"""



from zope.interface import implements

from twisted.plugin import IPlugin
from twisted.python.reflect import namedAny
from twisted.application.service import IServiceMaker, ISimpleServiceMaker, Service
from twisted.python.usage import Options



class RunOptions(Options):
    """
    Options for the C{run} plugin.
    """
    synopsis = "<fqpn> [service options]"

    longdesc = """
    Load the object at the given fully-qualified python name (fqpn), which
    should provide the IServiceMaker interface, and run the service that it
    makes. The specified [service options] will be processed by the service
    maker. For help on a given service maker, use::

      $ twistd run <fqpn> --help
    """


    def parseArgs(self, runner, *opts):
        """
        Parse command arguments: the service, and its options.
        """
        self['maker'] = runner
        self['maker_options'] = opts



class RunPlugin(object):
    """
    A plugin which delegates to another L{IServiceMaker} specified by a
    fully-qualified Python name.
    """
    implements(IPlugin, IServiceMaker)

    name = "Twisted Run Plugin"
    description = "A plugin to run services"
    tapname = "run"


    def options(self):
        """
        Return an instance of L{RunOptions}.
        """
        return RunOptions()


    def makeService(self, options):
        """
        Try to launch the specified service.

        @param options: Instance of L{RunOptions}.
        """
        try:
            maker = namedAny(options['maker'])
        except (ValueError, AttributeError):
            raise SystemExit(
                "Unable to import service named '%s'" % (options['maker'],))
        if ISimpleServiceMaker.providedBy(maker):
            subOptions = maker.options()
            subOptions.parseOptions(options['maker_options'])
            return maker.makeService(subOptions)
        else:
            main = getattr(maker, 'main')
            return FunctionService(main, list(options['maker_options']))
            #from twisted.internet import reactor
            #main(reactor, list(options['maker_options']))


class FunctionService(Service):
    """
    An L{IService} provider which will invoke a function when
    C{privilegedStartService} is called.

    @ivar _function: The function to invoke.
    @type _function: callable taking two arguments

    @ivar _args: Extra command-line arguments to pass to the function.
    @type _args: list of str
    """

    def __init__(self, function, args):
        self._function = function
        self._args = args

    def privilegedStartService(self):
        """
        Invoke C{self._function} with the global reactor and any extra arguments.
        """
        from twisted.internet import reactor
        self._function(reactor, self._args)


run = RunPlugin()
