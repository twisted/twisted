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
    Call the 'main' function in the specified Python module with the specified
    [service options]. For help on a given service maker, try::

      $ twistd run <fqpn> --help

    Alternatively, 'main' can be an IServiceMaker provider instead of a
    function.
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
    description = "Runs services from Python modules"
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
        # We could just call namedAny on the full path (modulename + '.main'),
        # but breaking it into multiple steps gives us the chance to provide
        # nicer error messages (when we can't find the module, we tell you
        # that we can't find the module; when we can't find 'main', we tell
        # you that.)
        try:
            maker = namedAny(options['maker'])
        except (ValueError, AttributeError):
            raise SystemExit(
                "Can't find Python object '%s'" % (options['maker'],))
        try:
            main = getattr(maker, 'main')
        except AttributeError:
            raise SystemExit("Can't find 'main' in '%s'" % (options['maker'],))

        if IServiceMaker.providedBy(main):
            subOptions = main.options()
            subOptions.parseOptions(options['maker_options'])
            return main.makeService(subOptions)
        else:
            from twisted.internet import reactor
            service = main(reactor, list(options['maker_options']))
            if service is None:
                return Service()
            else:
                return service


run = RunPlugin()
