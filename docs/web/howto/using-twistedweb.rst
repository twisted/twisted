
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Configuring and Using the Twisted Web Server
============================================






Twisted Web Development
-----------------------
.. _web-howto-using-twistedweb-development:








Twisted Web serves Python objects that implement the interface
IResource.






.. image:: ../img/web-process.png





Main Concepts
~~~~~~~~~~~~~





- :ref:`Site Objects <web-howto-using-twistedweb-sites>` are responsible for
  creating ``HTTPChannel`` instances to parse the HTTP request,
  and begin the object lookup process. They contain the root Resource,
  the resource which represents the URL ``/`` on the site.
- :ref:`Resource <web-howto-using-twistedweb-resources>` objects represent a single URL segment. The :api:`twisted.web.resource.IResource <IResource>` interface describes the methods a Resource object must implement in order to participate in the object publishing process.
- :ref:`Resource trees <web-howto-using-twistedweb-trees>` are arrangements of Resource objects into a Resource tree. Starting at the root Resource object, the tree of Resource objects defines the URLs which will be valid.
- :ref:`.rpy scripts <web-howto-using-twistedweb-rpys>` are python scripts which the twisted.web static file server will execute, much like a CGI. However, unlike CGI they must create a Resource object which will be rendered when the URL is visited.
- :ref:`Resource rendering <web-howto-using-twistedweb-rendering>` occurs when Twisted Web locates a leaf Resource object. A Resource can either return an html string or write to the request object.
- :ref:`Session <web-howto-using-twistedweb-sessions>` objects allow you to store information across multiple requests. Each individual browser using the system has a unique Session instance.





The Twisted Web server is started through the Twisted Daemonizer, as in:





.. code-block:: console

    
    % twistd web





Site Objects
~~~~~~~~~~~~

.. _web-howto-using-twistedweb-sites:








Site objects serve as the glue between a port to listen for HTTP requests on, and a root Resource object.




When using ``twistd -n web --path /foo/bar/baz`` , a Site object is created with a root Resource that serves files out of the given path.




You can also create a ``Site`` instance by hand, passing
it a ``Resource`` object which will serve as the root of the
site:





.. code-block:: python

    
    from twisted.web import server, resource
    from twisted.internet import reactor
    
    class Simple(resource.Resource):
        isLeaf = True
        def render_GET(self, request):
            return "<html>Hello, world!</html>"
    
    site = server.Site(Simple())
    reactor.listenTCP(8080, site)
    reactor.run()





Resource objects
~~~~~~~~~~~~~~~~

.. _web-howto-using-twistedweb-resources:








``Resource`` objects represent a single URL segment of a site. During URL parsing, ``getChild`` is called on the current ``Resource`` to produce the next ``Resource`` object.




When the leaf Resource is reached, either because there were no more URL segments or a Resource had isLeaf set to True, the leaf Resource is rendered by calling ``render(request)`` . See "Resource Rendering" below for more about this.




During the Resource location process, the URL segments which have already been processed and those which have not yet been processed are available in ``request.prepath`` and ``request.postpath`` .




A Resource can know where it is in the URL tree by looking at ``request.prepath`` , a list of URL segment strings.




A Resource can know which path segments will be processed after it by looking at ``request.postpath`` .




If the URL ends in a slash, for example ``http://example.com/foo/bar/`` , the final URL segment will be an empty string. Resources can thus know if they were requested with or without a final slash.




Here is a simple Resource object:





.. code-block:: python

    
    from twisted.web.resource import Resource
    
    class Hello(Resource):
        isLeaf = True
        def getChild(self, name, request):
            if name == '':
                return self
            return Resource.getChild(self, name, request)
    
        def render_GET(self, request):
            return "Hello, world! I am located at %r." % (request.prepath,)
    
    resource = Hello()





Resource Trees
~~~~~~~~~~~~~~

.. _web-howto-using-twistedweb-trees:








Resources can be arranged in trees using ``putChild`` . ``putChild`` puts a Resource instance into another Resource instance, making it available at the given path segment name:





.. code-block:: python

    
    root = Hello()
    root.putChild('fred', Hello())
    root.putChild('bob', Hello())




If this root resource is served as the root of a Site instance, the following URLs will all be valid:





- ``http://example.com/`` 
- ``http://example.com/fred`` 
- ``http://example.com/bob`` 
- ``http://example.com/fred/`` 
- ``http://example.com/bob/`` 






.rpy scripts
~~~~~~~~~~~~

.. _web-howto-using-twistedweb-rpys:








Files with the extension ``.rpy`` are python scripts which, when placed in a directory served by Twisted Web, will be executed when visited through the web.




An ``.rpy`` script must define a variable, ``resource`` , which is the Resource object that will render the request.




``.rpy`` files are very convenient for rapid development and prototyping. Since they are executed on every web request, defining a Resource subclass in an ``.rpy`` will make viewing the results of changes to your class visible simply by refreshing the page:





.. code-block:: python

    
    from twisted.web.resource import Resource
    
    class MyResource(Resource):
        def render_GET(self, request):
            return "<html>Hello, world!</html>"
    
    resource = MyResource()




However, it is often a better idea to define Resource subclasses in Python modules. In order for changes in modules to be visible, you must either restart the Python process, or reload the module:





.. code-block:: python

    
    import myresource
    
    ## Comment out this line when finished debugging
    reload(myresource)
    
    resource = myresource.MyResource()




Creating a Twisted Web server which serves a directory is easy:





.. code-block:: console

    
    % twistd -n web --path /Users/dsp/Sites





Resource rendering
~~~~~~~~~~~~~~~~~~

.. _web-howto-using-twistedweb-rendering:








Resource rendering occurs when Twisted Web locates a leaf Resource object to handle a web request. A Resource's ``render`` method may do various things to produce output which will be sent back to the browser:





- Return a string
- Call ``request.write("stuff")`` as many times as desired, then call ``request.finish()`` and return ``server.NOT_DONE_YET`` (This is deceptive, since you are in fact done with the request, but is the correct way to do this)
- Request a ``Deferred`` , return ``server.NOT_DONE_YET`` , and call ``request.write("stuff")`` and ``request.finish()`` later, in a callback on the ``Deferred`` .







The :api:`twisted.web.resource.Resource <Resource>` 
class, which is usually what one's Resource classes subclass, has a
convenient default implementation
of ``render`` . It will call a method
named ``self.render_METHOD`` 
where "METHOD" is whatever HTTP method was used to request this
resource. Examples: request_GET, request_POST, request_HEAD, and so
on. It is recommended that you have your resource classes
subclass :api:`twisted.web.resource.Resource <Resource>` 
and implement ``render_METHOD`` methods as
opposed to ``render`` itself. Note that for
certain resources, ``request_POST = request_GET`` may be desirable in case one wants to process
arguments passed to the resource regardless of whether they used GET
(``?foo=bar&baz=quux`` , and so forth) or POST.






Request encoders
~~~~~~~~~~~~~~~~




When using a :api:`twisted.web.resource.Resource <Resource>` ,
one can specify wrap it using a
:api:`twisted.web.resource.EncodingResourceWrapper <EncodingResourceWrapper>` 
and passing a list of encoder factories.  The encoder factories are
called when a request is processed and potentially return an encoder.
By default twisted provides
:api:`twisted.web.server.GzipEncoderFactory <GzipEncoderFactory>` which
manages standard gzip compression. You can use it this way:





.. code-block:: python

    
    from twisted.web.server import Site, GzipEncoderFactory
    from twisted.web.resource import Resource, EncodingResourceWrapper
    from twisted.internet import reactor
    
    class Simple(Resource):
        isLeaf = True
        def render_GET(self, request):
            return "<html>Hello, world!</html>"
    
    resource = Simple()
    wrapped = EncodingResourceWrapper(resource, [GzipEncoderFactory()])
    site = Site(wrapped)
    reactor.listenTCP(8080, site)
    reactor.run()





Using compression on SSL served resources where the user can influence the
content can lead to information leak, so be careful which resources use
request encoders.





Note that only encoder can be used per request: the first encoder factory
returning an object will be used, so the order in which they are specified
matters.





Session
~~~~~~~

.. _web-howto-using-twistedweb-sessions:








HTTP is a stateless protocol; every request-response is treated as an individual unit, distinguishable from any other request only by the URL requested. With the advent of Cookies in the mid nineties, dynamic web servers gained the ability to distinguish between requests coming from different *browser sessions* by sending a Cookie to a browser. The browser then sends this cookie whenever it makes a request to a web server, allowing the server to track which requests come from which browser session.




Twisted Web provides an abstraction of this browser-tracking behavior called the *Session object* . Calling ``request.getSession()`` checks to see if a session cookie has been set; if not, it creates a unique session id, creates a Session object, stores it in the Site, and returns it. If a session object already exists, the same session object is returned. In this way, you can store data specific to the session in the session object.





.. image:: ../img/web-session.png





Proxies and reverse proxies
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _web-howto-using-twistedweb-proxies:








A proxy is a general term for a server that functions as an intermediary
between clients and other servers.




Twisted supports two main proxy variants: a :api:`twisted.web.proxy.Proxy <Proxy>` and a :api:`twisted.web.proxy.ReverseProxy <ReverseProxy>` .





Proxy
^^^^^



A proxy forwards requests made by a client to a destination server. Proxies
typically sit on the internal network for a client or out on the internet, and
have many uses, including caching, packet filtering, auditing, and circumventing
local access restrictions to web content.




Here is an example of a simple but complete web proxy:





.. code-block:: python

    
    from twisted.web import proxy, http
    from twisted.internet import reactor
    
    class ProxyFactory(http.HTTPFactory):
        def buildProtocol(self, addr):
            return proxy.Proxy()
    
    reactor.listenTCP(8080, ProxyFactory())
    reactor.run()




With this proxy running, you can configure your web browser to use ``localhost:8080`` as a proxy. After doing so, when browsing the web
all requests will go through this proxy.




:api:`twisted.web.proxy.Proxy <Proxy>` inherits
from :api:`twisted.web.http.HTTPChannel <http.HTTPChannel>` . Each client
request to the proxy generates a :api:`twisted.web.proxy.ProxyRequest <ProxyRequest>` from the proxy to the destination
server on behalf of the client. ``ProxyRequest`` uses
a :api:`twisted.web.proxy.ProxyClientFactory <ProxyClientFactory>` to create
an instance of the :api:`twisted.web.proxy.ProxyClient <ProxyClient>` 
protocol for the connection. ``ProxyClient`` inherits
from :api:`twisted.web.http.HTTPClient <http.HTTPClient>` . Subclass ``ProxyRequest`` to
customize the way requests are processed or logged.





ReverseProxyResource
^^^^^^^^^^^^^^^^^^^^



A reverse proxy retrieves resources from other servers on behalf of a
client. Reverse proxies typically sit inside the server's internal network and
are used for caching, application firewalls, and load balancing.




Here is an example of a basic reverse proxy:





.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.web import proxy, server
    
    site = server.Site(proxy.ReverseProxyResource('www.yahoo.com', 80, ''))
    reactor.listenTCP(8080, site)
    reactor.run()




With this reverse proxy running locally, you can
visit ``http://localhost:8080`` in your web browser, and the reverse
proxy will proxy your connection to ``www.yahoo.com``.




In this example we use ``server.Site`` to serve
a ``ReverseProxyResource`` directly. There is
also a ``ReverseProxy`` family of classes
in ``twisted.web.proxy`` mirroring those of the ``Proxy`` 
family:




Like ``Proxy`` , :api:`twisted.web.proxy.ReverseProxy <ReverseProxy>` inherits
from ``http.HTTPChannel`` . Each client request to the reverse proxy
generates a :api:`twisted.web.proxy.ReverseProxyRequest <ReverseProxyRequest>` to the destination
server. Like ``ProxyRequest`` , :api:`twisted.web.proxy.ReverseProxyRequest <ReverseProxyRequest>` uses a :api:`twisted.web.proxy.ProxyClientFactory <ProxyClientFactory>` to create an instance of
the :api:`twisted.web.proxy.ProxyClient <ProxyClient>` protocol for
the connection.




Additional examples of proxies and reverse proxies can be found in
the `Twisted web examples <../examples/index.html>`_ 





Advanced Configuration
----------------------



Non-trivial configurations of Twisted Web are achieved with Python
configuration files. This is a Python snippet which builds up a
variable called application. Usually,
a ``twisted.application.internet.TCPServer`` 
instance will be used to make the application listen on a TCP port
(80, in case direct web serving is desired), with the listener being
a :api:`twisted.web.server.Site <twisted.web.server.Site>` . The resulting file
can then be run with ``twistd -y`` . Alternatively a reactor object can be used directly to make
a runnable script.




The ``Site`` will wrap a ``Resource`` object -- the
root.





.. code-block:: python

    
    from twisted.application import internet, service
    from twisted.web import static, server
    
    root = static.File("/var/www/htdocs")
    application = service.Application('web')
    site = server.Site(root)
    sc = service.IServiceCollection(application)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)




Most advanced configurations will be in the form of tweaking the
root resource object.





Adding Children
~~~~~~~~~~~~~~~



Usually, the root's children will be based on the filesystem's contents.
It is possible to override the filesystem by explicit ``putChild`` 
methods.




Here are two examples. The first one adds a ``/doc`` child
to serve the documentation of the installed packages, while the second
one adds a ``cgi-bin`` directory for CGI scripts.





.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.web import static, server
    
    root = static.File("/var/www/htdocs")
    root.putChild("doc", static.File("/usr/share/doc"))
    reactor.listenTCP(80, server.Site(root))
    reactor.run()





.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.web import static, server, twcgi
    
    root = static.File("/var/www/htdocs")
    root.putChild("cgi-bin", twcgi.CGIDirectory("/var/www/cgi-bin"))
    reactor.listenTCP(80, server.Site(root))
    reactor.run()





Modifying File Resources
~~~~~~~~~~~~~~~~~~~~~~~~



``File`` resources, be they root object or children
thereof, have two important attributes that often need to be
modified: ``indexNames`` 
and ``processors`` . ``indexNames`` determines which
files are treated as "index files" -- served up when a directory
is rendered. ``processors`` determine how certain file
extensions are treated.




Here is an example for both, creating a site where all ``.rpy`` 
extensions are Resource Scripts, and which renders directories by
searching for a ``index.rpy`` file.





.. code-block:: python

    
    from twisted.application import internet, service
    from twisted.web import static, server, script
    
    root = static.File("/var/www/htdocs")
    root.indexNames=['index.rpy']
    root.processors = {'.rpy': script.ResourceScript}
    application = service.Application('web')
    sc = service.IServiceCollection(application)
    site = server.Site(root)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)




``File`` objects also have a method called ``ignoreExt`` .
This method can be used to give extension-less URLs to users, so that
implementation is hidden. Here is an example:





.. code-block:: python

    
    from twisted.application import internet, service
    from twisted.web import static, server, script
    
    root = static.File("/var/www/htdocs")
    root.ignoreExt(".rpy")
    root.processors = {'.rpy': script.ResourceScript}
    application = service.Application('web')
    sc = service.IServiceCollection(application)
    site = server.Site(root)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)




Now, a URL such as ``/foo`` might be served from a Resource
Script called ``foo.rpy`` , if no file by the name of ``foo`` 
exists.





Virtual Hosts
~~~~~~~~~~~~~



Virtual hosting is done via a special resource, that should be used
as the root resource
-- ``NameVirtualHost`` . ``NameVirtualHost`` has an
attribute named ``default`` , which holds the default
website. If a different root for some other name is desired,
the ``addHost`` method should be called.





.. code-block:: python

    
    from twisted.application import internet, service
    from twisted.web import static, server, vhost, script
    
    root = vhost.NameVirtualHost()
    
    # Add a default -- htdocs
    root.default=static.File("/var/www/htdocs")
    
    # Add a simple virtual host -- foo.com
    root.addHost("foo.com", static.File("/var/www/foo"))
    
    # Add a simple virtual host -- bar.com
    root.addHost("bar.com", static.File("/var/www/bar"))
    
    # The "baz" people want to use Resource Scripts in their web site
    baz = static.File("/var/www/baz")
    baz.processors = {'.rpy': script.ResourceScript}
    baz.ignoreExt('.rpy')
    root.addHost('baz', baz)
    
    application = service.Application('web')
    sc = service.IServiceCollection(application)
    site = server.Site(root)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)





Advanced Techniques
~~~~~~~~~~~~~~~~~~~



Since the configuration is a Python snippet, it is possible to
use the full power of Python. Here are some simple examples:





.. code-block:: python

    
    # No need for configuration of virtual hosts -- just make sure
    # a directory /var/vhosts/<vhost name> exists:
    from twisted.web import vhost, static, server
    from twisted.application import internet, service
    
    root = vhost.NameVirtualHost()
    root.default = static.File("/var/www/htdocs")
    for dir in os.listdir("/var/vhosts"):
        root.addHost(dir, static.File(os.path.join("/var/vhosts", dir)))
    
    application = service.Application('web')
    sc = service.IServiceCollection(application)
    site = server.Site(root)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)





.. code-block:: python

    
    # Determine ports we listen on based on a file with numbers:
    from twisted.web import vhost, static, server
    from twisted.application import internet, service
    
    root = static.File("/var/www/htdocs")
    
    site = server.Site(root)
    application = service.Application('web')
    serviceCollection = service.IServiceCollection(application)
    
    for num in map(int, open("/etc/web/ports").read().split()):
        serviceCollection.addCollection(internet.TCPServer(num, site))






Running a Twisted Web Server
----------------------------



In many cases, you'll end up repeating common usage patterns of
twisted.web. In those cases you'll probably want to use Twisted's
pre-configured web server setup.




The easiest way to run a Twisted Web server is with the Twisted Daemonizer.
For example, this command will run a web server which serves static files from
a particular directory:





.. code-block:: console

    
    % twistd web --path /path/to/web/content




If you just want to serve content from your own home directory, the
following will do:





.. code-block:: console

    
    % twistd web --path ~/public_html/




You can stop the server at any time by going back to the directory you
started it in and running the command:





.. code-block:: console

    
    % kill `cat twistd.pid`




Some other configuration options are available as well:  






- ``--port`` : Specify the port for the web
  server to listen on.  This defaults to 8080.  
- ``--logfile`` : Specify the path to the
  log file. 





The full set of options that are available can be seen with:  





.. code-block:: console

    
    % twistd web --help





Serving Flat HTML
~~~~~~~~~~~~~~~~~



Twisted Web serves flat HTML files just as it does any other flat file.  



.. _web-howto-using-twistedweb-resourcescripts:








Resource Scripts
~~~~~~~~~~~~~~~~



A Resource script is a Python file ending with the extension ``.rpy`` , which is required to create an instance of a (subclass of a) :api:`twisted.web.resource.Resource <twisted.web.resource.Resource>` . 




Resource scripts have 3 special variables: 






- ``__file__`` : The name of the .rpy file, including the full path.  This variable is automatically defined and present within the namespace.  
- ``registry`` : An object of class :api:`twisted.web.static.Registry <static.Registry>` . It can be used to access and set persistent data keyed by a class.
- ``resource`` : The variable which must be defined by the script and set to the resource instance that will be used to render the page. 





A very simple Resource Script might look like:  





.. code-block:: python

    
    from twisted.web import resource
    class MyGreatResource(resource.Resource):
        def render_GET(self, request):
            return "<html>foo</html>"
    
    resource = MyGreatResource()




A slightly more complicated resource script, which accesses some
persistent data, might look like:





.. code-block:: python

    
    from twisted.web import resource
    from SillyWeb import Counter
    
    counter = registry.getComponent(Counter)
    if not counter:
       registry.setComponent(Counter, Counter())
    counter = registry.getComponent(Counter)
    
    class MyResource(resource.Resource):
        def render_GET(self, request):
            counter.increment()
            return "you are visitor %d" % counter.getValue()
    
    resource = MyResource()




This is assuming you have the ``SillyWeb.Counter`` module,
implemented something like the following:





.. code-block:: python

    
    class Counter:
    
        def __init__(self):
            self.value = 0
    
        def increment(self):
            self.value += 1
    
        def getValue(self):
            return self.value





Web UIs
~~~~~~~




The `Nevow <https://launchpad.net/nevow>`_ framework, available as
part of the `Quotient <https://launchpad.net/quotient>`_ project,
is an advanced system for giving Web UIs to your application. Nevow uses Twisted Web but is
not itself part of Twisted.



.. _web-howto-using-twistedweb-spreadablewebservers:








Spreadable Web Servers
~~~~~~~~~~~~~~~~~~~~~~



One of the most interesting applications of Twisted Web is the distributed webserver; multiple servers can all answer requests on the same port, using the :api:`twisted.spread <twisted.spread>` package for "spreadable" computing.  In two different directories, run the commands:  





.. code-block:: console

    
    % twistd web --user
    % twistd web --personal [other options, if you desire]




Once you're running both of these instances, go to ``http://localhost:8080/your_username.twistd/`` -- you will see the front page from the server you created with the ``--personal`` option.  What's happening here is that the request you've sent is being relayed from the central (User) server to your own (Personal) server, over a PB connection.  This technique can be highly useful for small "community" sites; using the code that makes this demo work, you can connect one HTTP port to multiple resources running with different permissions on the same machine, on different local machines, or even over the internet to a remote site.  





By default, a personal server listens on a UNIX socket in the owner's home
directory.  The ``--port`` option can be used to make
it listen on a different address, such as a TCP or SSL server or on a UNIX
server in a different location.  If you use this option to make a personal
server listen on a different address, the central (User) server won't be
able to find it, but a custom server which uses the same APIs as the central
server might.  Another use of the ``--port`` option
is to make the UNIX server robust against system crashes.  If the server
crashes and the UNIX socket is left on the filesystem, the personal server
will not be able to restart until it is removed.  However, if ``--port unix:/home/username/.twistd-web-pb:wantPID=1`` is
supplied when creating the personal server, then a lockfile will be used to
keep track of whether the server socket is in use and automatically delete
it when it is not.





Serving PHP/Perl/CGI
~~~~~~~~~~~~~~~~~~~~



Everything related to CGI is located in
the ``twisted.web.twcgi`` , and it's here you'll find the
classes that you need to subclass in order to support the language of
your (or somebody elses) taste. You'll also need to create your own
kind of resource if you are using a non-unix operating system (such as
Windows), or if the default resources has wrong pathnames to the
parsers.




The following snippet is a .rpy that serves perl-files. Look at ``twisted.web.twcgi`` 
for more examples regarding twisted.web and CGI.





.. code-block:: python

    
    from twisted.web import static, twcgi
    
    class PerlScript(twcgi.FilteredScript):
        filter = '/usr/bin/perl' # Points to the perl parser
    
    resource = static.File("/perlsite") # Points to the perl website
    resource.processors = {".pl": PerlScript} # Files that end with .pl will be
                                              # processed by PerlScript
    resource.indexNames = ['index.pl']





Serving WSGI Applications
~~~~~~~~~~~~~~~~~~~~~~~~~



`WSGI <http://wsgi.org>`_ is the Web Server Gateway
Interface. It is a specification for web servers and application servers to
communicate with Python web applications. All modern Python web frameworks
support the WSGI interface.




The easiest way to get started with WSGI application is to use the twistd
command:





.. code-block:: console

    
    % twistd -n web --wsgi=helloworld.application




This assumes that you have a WSGI application called application in
your helloworld module/package, which might look like this:





.. code-block:: python

    
    def application(environ, start_response):
        """Basic WSGI Application"""
        start_response('200 OK', [('Content-type','text/plain')])
        return ['Hello World!']




The above setup will be suitable for many applications where all that is
needed is to server the WSGI application at the site's root. However, for
greater control, Twisted provides support for using WSGI applications as
resources ``twisted.web.wsgi.WSGIResource`` .




Here is an example of a WSGI application being served as the root resource
for a site, in the following tac file:





.. code-block:: python

    
    from twisted.web import server
    from twisted.web.wsgi import WSGIResource
    from twisted.python.threadpool import ThreadPool
    from twisted.internet import reactor
    from twisted.application import service, strports
    
    # Create and start a thread pool,
    wsgiThreadPool = ThreadPool()
    wsgiThreadPool.start()
    
    # ensuring that it will be stopped when the reactor shuts down
    reactor.addSystemEventTrigger('after', 'shutdown', wsgiThreadPool.stop)
    
    def application(environ, start_response):
        """A basic WSGI application"""
        start_response('200 OK', [('Content-type','text/plain')])
        return ['Hello World!']
    
    # Create the WSGI resource
    wsgiAppAsResource = WSGIResource(reactor, wsgiThreadPool, application)
    
    # Hooks for twistd
    application = service.Application('Twisted.web.wsgi Hello World Example')
    server = strports.service('tcp:8080', server.Site(wsgiAppAsResource))
    server.setServiceParent(application)




This can then be run like any other .tac file:





.. code-block:: console

    
    % twistd -ny myapp.tac




Because of the synchronous nature of WSGI, each application call (for
each request) is called within a thread, and the result is written back to the
web server. For this, a ``twisted.python.threadpool.ThreadPool`` 
instance is used.





Using VHostMonster
~~~~~~~~~~~~~~~~~~



It is common to use one server (for example, Apache) on a site with multiple
names which then uses reverse proxy (in Apache, via ``mod_proxy`` ) to different
internal web servers, possibly on different machines. However, naive
configuration causes miscommunication: the internal server firmly believes it
is running on "internal-name:port" , and will generate URLs to that effect,
which will be completely wrong when received by the client.




While Apache has the ProxyPassReverse directive, it is really a hack
and is nowhere near comprehensive enough. Instead, the recommended practice
in case the internal web server is Twisted Web is to use VHostMonster.




From the Twisted side, using VHostMonster is easy: just drop a file named
(for example) ``vhost.rpy`` containing the following:





.. code-block:: python

    
    from twisted.web import vhost
    resource = vhost.VHostMonsterResource()




Make sure the web server is configured with the correct processors
for the ``rpy`` extensions (the web server ``twistd web --path`` generates by default is so configured).




From the Apache side, instead of using the following ProxyPass directive:





::

    
    <VirtualHost ip-addr>
    ProxyPass / http://localhost:8538/
    ServerName example.com
    </VirtualHost>




Use the following directive:





::

    
    <VirtualHost ip-addr>
    ProxyPass / http://localhost:8538/vhost.rpy/http/example.com:80/
    ServerName example.com
    </VirtualHost>




Here is an example for Twisted Web's reverse proxy:





.. code-block:: python

    
    from twisted.application import internet, service
    from twisted.web import proxy, server, vhost
    vhostName = 'example.com'
    reverseProxy = proxy.ReverseProxyResource('internal', 8538,
                                              '/vhost.rpy/http/'+vhostName+'/')
    root = vhost.NameVirtualHost()
    root.addHost(vhostName, reverseProxy)
    site = server.Site(root)
    application = service.Application('web-proxy')
    sc = service.IServiceCollection(application)
    i = internet.TCPServer(80, site)
    i.setServiceParent(sc)





Rewriting URLs
--------------



Sometimes it is convenient to modify the content of
the :api:`twisted.web.server.Request <Request>` object
before passing it on. Because this is most often used to rewrite
either the URL, the similarity to Apache's ``mod_rewrite`` 
has inspired the :api:`twisted.web.rewrite <twisted.web.rewrite>` 
module. Using this module is done via wrapping a resource with
a :api:`twisted.web.rewrite.RewriterResource <twisted.web.rewrite.RewriterResource>` which
then has rewrite rules. Rewrite rules are functions which accept a
request object, and possible modify it. After all rewrite rules run,
the child resolution chain continues as if the wrapped resource,
rather than the :api:`twisted.web.rewrite.RewriterResource <RewriterResource>` , was the child.




Here is an example, using the only rule currently supplied by Twisted
itself:





.. code-block:: python

    
    default_root = rewrite.RewriterResource(default, rewrite.tildeToUsers)




This causes the URL ``/~foo/bar.html`` to be treated
like ``/users/foo/bar.html`` . If done after setting
default's ``users`` child to a :api:`twisted.web.distrib.UserDirectory <distrib.UserDirectory>` , it gives a
configuration similar to the classical configuration of web server,
common since the first NCSA servers.





Knowing When We're Not Wanted
-----------------------------



Sometimes it is useful to know when the other side has broken the connection.
Here is an example which does that:





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web import server
    from twisted.internet import reactor
    from twisted.python.util import println
    
    
    class ExampleResource(Resource):
    
        def render_GET(self, request):
            request.write("hello world")
            d = request.notifyFinish()
            d.addCallback(lambda _: println("finished normally"))
            d.addErrback(println, "error")
            reactor.callLater(10, request.finish)
            return server.NOT_DONE_YET
    
    resource = ExampleResource()




This will allow us to run statistics on the log-file to see how many users
are frustrated after merely 10 seconds.





As-Is Serving
-------------



Sometimes, you want to be able to send headers and status
directly. While you can do this with a :api:`twisted.web.script.ResourceScript <ResourceScript>` , an easier way is to
use :api:`twisted.web.static.ASISProcessor <ASISProcessor>` .
Use it by, for example, adding it as a processor for
the ``.asis`` extension. Here is a sample file:





::

    
    HTTP/1.0 200 OK
    Content-Type: text/html
    
    Hello world



