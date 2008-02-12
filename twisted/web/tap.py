# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for creating a service which runs a web server.
"""

import os

# Twisted Imports
from twisted.web import server, static, twcgi, script, demo, distrib, trp
from twisted.internet import interfaces
from twisted.python import usage, reflect
from twisted.spread import pb
from twisted.application import internet, service, strports


class Options(usage.Options):
    synopsis = "Usage: mktap web [options]"
    optParameters = [["port", "p", "8080","Port to start the server on."],
                     ["logfile", "l", None, "Path to web CLF (Combined Log Format) log file."],
                     ["https", None, None, "Port to listen on for Secure HTTP."],
                     ["certificate", "c", "server.pem", "SSL certificate to use for HTTPS. "],
                     ["privkey", "k", "server.pem", "SSL certificate to use for HTTPS."],
                     ]
    optFlags = [["personal", "",
                 "Instead of generating a webserver, generate a "
                 "ResourcePublisher which listens on "
                 "~/%s" % distrib.UserDirectory.userSocketName],
                ["notracebacks", "n", "Display tracebacks in broken web pages. " +
                 "Displaying tracebacks to users may be security risk!"],
]
    zsh_actions = {"logfile" : "_files -g '*.log'", "certificate" : "_files -g '*.pem'",
                   "privkey" : "_files -g '*.pem'"}


    longdesc = """\
This creates a web.tap file that can be used by twistd.  If you specify
no arguments, it will be a demo webserver that has the Test class from
twisted.web.demo in it."""

    def __init__(self):
        usage.Options.__init__(self)
        self['indexes'] = []
        self['root'] = None

    def opt_index(self, indexName):
        """Add the name of a file used to check for directory indexes.
        [default: index, index.html]
        """
        self['indexes'].append(indexName)

    opt_i = opt_index

    def opt_user(self):
        """Makes a server with ~/public_html and ~/.twistd-web-pb support for
        users.
        """
        self['root'] = distrib.UserDirectory()

    opt_u = opt_user

    def opt_path(self, path):
        """<path> is either a specific file or a directory to
        be set as the root of the web server. Use this if you
        have a directory full of HTML, cgi, php3, epy, or rpy files or
        any other files that you want to be served up raw.
        """

        self['root'] = static.File(os.path.abspath(path))
        self['root'].processors = {
            '.cgi': twcgi.CGIScript,
            '.php3': twcgi.PHP3Script,
            '.php': twcgi.PHPScript,
            '.epy': script.PythonScript,
            '.rpy': script.ResourceScript,
            '.trp': trp.ResourceUnpickler,
            }

    def opt_processor(self, proc):
        """`ext=class' where `class' is added as a Processor for files ending
        with `ext'.
        """
        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --processor after --path.")
        ext, klass = proc.split('=', 1)
        self['root'].processors[ext] = reflect.namedClass(klass)

    def opt_static(self, path):
        """Same as --path, this is deprecated and will be removed in a
        future release."""
        print ("WARNING: --static is deprecated and will be removed in"
               "a future release. Please use --path.")
        self.opt_path(path)
    opt_s = opt_static

    def opt_class(self, className):
        """Create a Resource subclass with a zero-argument constructor.
        """
        classObj = reflect.namedClass(className)
        self['root'] = classObj()


    def opt_resource_script(self, name):
        """An .rpy file to be used as the root resource of the webserver."""
        self['root'] = script.ResourceScriptWrapper(name)


    def opt_mime_type(self, defaultType):
        """Specify the default mime-type for static files."""
        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --mime_type after --path.")
        self['root'].defaultType = defaultType
    opt_m = opt_mime_type


    def opt_allow_ignore_ext(self):
        """Specify whether or not a request for 'foo' should return 'foo.ext'"""
        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --allow_ignore_ext "
                                   "after --path.")
        self['root'].ignoreExt('*')

    def opt_ignore_ext(self, ext):
        """Specify an extension to ignore.  These will be processed in order.
        """
        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --ignore_ext "
                                   "after --path.")
        self['root'].ignoreExt(ext)

    def opt_flashconduit(self, port=None):
        """Start a flashconduit on the specified port.
        """
        if not port:
            port = "4321"
        self['flashconduit'] = port

    def postOptions(self):
        if self['https']:
            try:
                from twisted.internet.ssl import DefaultOpenSSLContextFactory
            except ImportError:
                raise usage.UsageError("SSL support not installed")



def makePersonalServerFactory(site):
    """
    Create and return a factory which will respond to I{distrib} requests
    against the given site.

    @type site: L{twisted.web.server.Site}
    @rtype: L{twisted.internet.protocol.Factory}
    """
    return pb.PBServerFactory(distrib.ResourcePublisher(site))



def makeService(config):
    s = service.MultiService()
    if config['root']:
        root = config['root']
        if config['indexes']:
            config['root'].indexNames = config['indexes']
    else:
        # This really ought to be web.Admin or something
        root = demo.Test()

    if isinstance(root, static.File):
        root.registry.setComponent(interfaces.IServiceCollection, s)

    if config['logfile']:
        site = server.Site(root, logPath=config['logfile'])
    else:
        site = server.Site(root)

    site.displayTracebacks = not config["notracebacks"]

    if config['personal']:
        import pwd
        name, passwd, uid, gid, gecos, dir, shell = pwd.getpwuid(os.getuid())
        personal = internet.UNIXServer(
            os.path.join(dir, distrib.UserDirectory.userSocketName),
            makePersonalServerFactory(site))
        personal.setServiceParent(s)
    else:
        if config['https']:
            from twisted.internet.ssl import DefaultOpenSSLContextFactory
            i = internet.SSLServer(int(config['https']), site,
                          DefaultOpenSSLContextFactory(config['privkey'],
                                                       config['certificate']))
            i.setServiceParent(s)
        strports.service(config['port'], site).setServiceParent(s)

    flashport = config.get('flashconduit', None)
    if flashport:
        from twisted.web.woven.flashconduit import FlashConduitFactory
        i = internet.TCPServer(int(flashport), FlashConduitFactory(site))
        i.setServiceParent(s)
    return s
