
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

WSGI
====





The goal of this example is to show you how to
use :api:`twisted.web.wsgi.WSGIResource <WSGIResource>` ,
another existing :api:`twisted.web.resource.Resource <Resource>` subclass, to
serve `WSGI applications <http://www.python.org/dev/peps/pep-0333/>`_ 
in a Twisted Web server.




Note that ``WSGIResource`` is a multithreaded WSGI container. Like
any other WSGI container, you can't do anything asynchronous in your WSGI
applications, even though this is a Twisted WSGI container.




The first new thing in this example is the import
of ``WSGIResource`` :





.. code-block:: python

    
    from twisted.web.wsgi import WSGIResource




Nothing too surprising there. We still need one of the other usual suspects,
too:





.. code-block:: python

    
    from twisted.internet import reactor




You'll see why in a minute. Next, we need a WSGI application. Here's a really
simple one just to get things going:





.. code-block:: python

    
    def application(environ, start_response):
        start_response('200 OK', [('Content-type', 'text/plain')])
        return ['Hello, world!']




If this doesn't make sense to you, take a look at one of
these `fine tutorials <http://wsgi.readthedocs.org/en/latest/learn.html>`_ . Otherwise,
or once you're done with that, the next step is to create
a ``WSGIResource`` instance, as this is going to be
another :doc:`rpy script <rpy-scripts>` example:





.. code-block:: python

    
    resource = WSGIResource(reactor, reactor.getThreadPool(), application)




Let's dwell on this line for a minute. The first parameter passed
to ``WSGIResource`` is the reactor. Despite the fact that the
reactor is global and any code that wants it can always just import it
(as, in fact, this rpy script simply does itself), passing it around
as a parameter leaves the door open for certain future possibilities -
for example, having more than one reactor. There are also testing
implications. Consider how much easier it is to unit test a function
that accepts a reactor - perhaps a mock reactor specially constructed
to make your tests easy to write - rather than importing the real
global reactor. That's why ``WSGIResource`` requires you to
pass the reactor to it.




The second parameter passed to ``WSGIResource`` is
a :api:`twisted.python.threadpool.ThreadPool <ThreadPool>` . ``WSGIResource`` 
uses this to actually call the application object passed in to it. To keep this
example short, we're passing in the reactor's internal threadpool here, letting
us skip its creation and shutdown-time destruction. For finer control over how
many WSGI requests are served in parallel, you may want to create your own
thread pool to use with your ``WSGIResource`` , but for simple testing,
using the reactor's is fine.




The final argument is the application object. This is pretty typical of how
WSGI containers work.




The example, sans interruption:





.. code-block:: python

    
    from twisted.web.wsgi import WSGIResource
    from twisted.internet import reactor
    
    def application(environ, start_response):
        start_response('200 OK', [('Content-type', 'text/plain')])
        return ['Hello, world!']
    
    resource = WSGIResource(reactor, reactor.getThreadPool(), application)




Up to the point where the ``WSGIResource`` instance defined here
exists in the resource hierarchy, the normal resource traversal rules
apply: :api:`twisted.web.resource.Resource.getChild <getChild>` 
will be called to handle each segment. Once the ``WSGIResource`` is
encountered, though, that process stops and all further URL handling is the
responsibility of the WSGI application. This application does nothing with the
URL, though, so you won't be able to tell that.




Oh, and as was the case with the first static file example, there's also a
command line option you can use to avoid a lot of this. If you just put the
above application function, without all of the ``WSGIResource`` stuff,
into a file, say, ``foo.py`` , then you can launch a roughly equivalent
server like this:





.. code-block:: console

    
    $ twistd -n web --wsgi foo.application



