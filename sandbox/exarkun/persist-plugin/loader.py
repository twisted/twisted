
class IApplicationLoader(components.Interface):
    def getParameter(self):
        """Return a description of the command-line invocation of this loader.

        @return: A 4-tuple suitable for use as an element of a
        C{twisted.python.usage.Options.optParameters} list.
        """

    def getApplication(self, argument, passphrase):
        """Load and return an application.

        @type argument: C{str}
        @param argument: The argument specified on the command line.

        @rtype: C{Componentized}
        @return: An object suitable for use as an application.
        """

class _BasicLoader:
    __implements__ = IApplicationLoader

    def getParameter(self):
        return [self.long, self.short, None, self.desc]

    def getApplication(self, argument, passphrase):
        try:
            log.msg("Loading %s..." % argument)
            application = service.loadApplication(argument, self.type, passphrase)
            log.msg("Loaded.")
        except Exception, e:
            s = "Failed to load application: %s" % e
            if isinstance(e, KeyError) and e.args[0] == "application":
                s += """
Could not find 'application' in the file. To use 'twistd -y', your .tac
file must create a suitable object (e.g., by calling service.Application())
and store it in a variable named 'application'. twistd loads your .tac file
and scans the global variables for one of this name.

Please read the 'Using Application' HOWTO for details.
"""
                traceback.print_exc(file=log.logfile)
                log.msg(s)
                log.err()
                raise SystemError('\n' + s + '\n')
        else:
            return application

class TAPLoader(_BasicLoader):
    long = 'file'
    short = 'f'
    desc = "read the given .tap file"
    type = 'pickle'

class TAXLoader(_BasicLoader):
    type = long = 'xml'
    short = 'x'
    desc = "read the given .tax file"

class TASLoader(_BasicLoader):
    type = long = 'source'
    short = 's'
    desc = 'read the given .tas file'
