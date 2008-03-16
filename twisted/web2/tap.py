import os
from zope.interface import implements

from twisted.python import usage, reflect
from twisted.application import internet, service, strports
from twisted.scripts.mktap import IServiceMaker
from twisted.plugin import IPlugin

from twisted.web2 import static, iweb, log, server, channel, vhost

class Options(usage.Options):
    optParameters = [["port", "p", "8080",
                      "Port to start the server on."],
                     ["logfile", "l", None,
                      ("Common Access Logging Format file to write to "
                       "if unspecified access log information will be "
                       "written to the standard twisted log file.")],
                     ["https", None, None,
                      "Port to listen on for Secure HTTP."],
                     ["certificate", "c", "server.pem",
                      "SSL certificate to use for HTTPS."],
                     ["privkey", "k", "server.pem",
                      "SSL certificate to use for HTTPS."]]
    
    zsh_actions = {"certificate" : "_files -g '*.pem'",
                   "privkey" : "_files -g '*.pem'"}
    
    longdesc = """\
This creates a web2.tap file that can be used by twistd.

Basic Examples:

To serve a static directory or file:

    mktap web2 --path=/tmp/

To serve a dynamic resource:

    mktap web2 --class=fully.qualified.ClassName

To serve a directory of the form:

    /var/www/domain1/
    /var/www/domain2/

    mktap web2 --vhost-path=/var/www/

All the above options are incompatible as they all specify the
root resource.  However you can use the following options in
conjunction with --vhost-path

To serve a specific host name as a static file:

    mktap web2 --vhost-static=domain3=/some/other/root/domain3

Or to serve a specific host name as a dynamic resource:

    mktap web2 --vhost-class=domain4=fully.qualified.ClassName

"""

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

    def opt_path(self, path):
        """A path that will be used to serve the root resource as a raw file
        or directory.
        """

        if self['root']:
            raise usage.UsageError("You may only have one root resource.")

        self['root'] = static.File(os.path.abspath(path))

    def opt_processor(self, proc):
        """`ext=class' where `class' is added as a Processor for files ending
        with `ext'.
        """
        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --processor after --path.")
        ext, klass = proc.split('=', 1)
        self['root'].processors[ext] = reflect.namedClass(klass)

    def opt_class(self, className):
        """A class that will be used to serve the root resource.  Must implement twisted.web2.iweb.IResource and take no arguments.
        """
        if self['root']:
            raise usage.UsageError("You may only have one root resource.")
        
        classObj = reflect.namedClass(className)
        self['root'] = iweb.IResource(classObj())

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

    def opt_mimetype(self, mimetype):
        """Mapping from file extension to MIME Type in the form of 'ext=type'.
        Example: html=text/html
        """

        if not isinstance(self['root'], static.File):
            raise usage.UsageError("You can only use --mimetype "
                                   "after --path.")

        ext, mimetype = mimetype.split('=', 1)

        # this is really gross, there should be a public api for this.
        
        self['root']._sharedContentTypes.update({ext: mimetype})

    def opt_vhost_path(self, path):
        """Specify a directory to use for automatic named virtual hosts.
        It is assumed that this directory contains a series of
        subdirectories each representing a virtual host domain name
        and containing the files to be served at that domain.
        """
        
        if self['root']:
            if not isintance(self['root'], vhost.NameVirtualHost):
                raise usage.UsageError("You may only have one root resource")
        else:
            self['root'] = vhost.NameVirtualHost()

        path = os.path.abspath(path)
        
        for name in os.listdir(path):
            fullname = os.path.join(path, name)
            self['root'].addHost(name,
                                 static.File(fullname))

    def opt_vhost_static(self, virtualHost):
        """Specify a virtual host in the form of domain=path to be served as
        raw directory or file.
        """
        if (self['root'] and not \
            isinstance(self['root'], vhost.NameVirtualHost)):

            raise usage.UsageError("You can only use --vhost-static alone "
                                   "or with --vhost-class and --vhost-path")

        domain, path = virtualHost.split('=', 1)

        if not self['root']:
            self['root'] = vhost.NameVirtualHost()

        self['root'].addHost(domain, static.File(os.path.abspath(path)))
    
    def opt_vhost_class(self, virtualHost):
        """Specify a virtual host in the form of domain=class,
        where class can be adapted to an iweb.IResource and has a
        zero-argument constructor.
        """
        if (self['root'] and not \
            isinstance(self['root'], vhost.NameVirtualHost)):

            raise usage.UsageError("You can not use --vhost-class with "
                                   "--path or --class.")

        domain, className = virtualHost.split('=', 1)

        if not self['root']:
            self['root'] = vhost.NameVirtualHost()

        classObj = reflect.namedClass(className)
        self['root'].addHost(domain, iweb.IResource(classObj()))

    def postOptions(self):
        if self['https']:
            try:
                from twisted.internet.ssl import DefaultOpenSSLContextFactory
            except ImportError:
                raise usage.UsageError("SSL support not installed")


class Web2Service(service.MultiService):
    def __init__(self, logObserver):
        self.logObserver = logObserver
        service.MultiService.__init__(self)

    def startService(self):
        service.MultiService.startService(self)
        self.logObserver.start()

    def stopService(self):
        service.MultiService.stopService(self)
        self.logObserver.stop()


def makeService(config):
    if config['logfile']:
        logObserver = log.FileAccessLoggingObserver(config['logfile'])
    else:
        logObserver = log.DefaultCommonAccessLoggingObserver()

    if config['root']:
        if config['indexes']:
            config['root'].indexNames = config['indexes']
            
        root = log.LogWrapperResource(config['root'])


    s = Web2Service(logObserver)

    site = server.Site(root)
    chan = channel.HTTPFactory(site)
    
    if config['https']:
        from twisted.internet.ssl import DefaultOpenSSLContextFactory
        i = internet.SSLServer(int(config['https']), chan,
                               DefaultOpenSSLContextFactory(config['privkey'],
                                                            config['certificate']))
        i.setServiceParent(s)
        
    strports.service(config['port'], chan
                     ).setServiceParent(s)

    return s
