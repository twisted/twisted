
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Serving Static Content From a Directory
=======================================





The goal of this example is to show you how to serve static content
from a filesystem. First, we need to import some objects:






- :api:`twisted.web.server.Site <Site>` , an :api:`twisted.internet.interfaces.IProtocolFactory <IProtocolFactory>` which
  glues a listening server port (:api:`twisted.internet.interfaces.IListeningPort <IListeningPort>` ) to the :api:`twisted.web.http.HTTPChannel <HTTPChannel>` 
  implementation:
  
  .. code-block:: python
  
      from twisted.web.server import Site
  
- :api:`twisted.web.static.File <File>` , an :api:`twisted.web.resource.IResource <IResource>` which glues
  the HTTP protocol implementation to the filesystem:
  
  .. code-block:: python
  
      from twisted.web.static import File
  
- 
  The :api:`twisted.internet.reactor <reactor>` , which
  drives the whole process, actually accepting TCP connections and
  moving bytes into and out of them:
  
  .. code-block:: python
  
      from twisted.internet import reactor
  


Next, we create an instance of the File resource pointed at the
directory to serve:




.. code-block:: python

    resource = File("/tmp")



Then we create an instance of the Site factory with that resource:


.. code-block:: python

    factory = Site(resource)



Now we glue that factory to a TCP port:


.. code-block:: python

    reactor.listenTCP(8888, factory)



Finally, we start the reactor so it can make the program work:


.. code-block:: python

    reactor.run()


And that's it. Here's the complete program:



.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.static import File
    from twisted.internet import reactor
    
    resource = File('/tmp')
    factory = Site(resource)
    reactor.listenTCP(8888, factory)
    reactor.run()




Bonus example! For those times when you don't actually want to
write a new program, the above implemented functionality is one of the
things the command line ``twistd`` tool can do. In this case,
the command

::

    
    twistd -n web --path /tmp


will accomplish the same thing as the above server. See :doc:`helper programs <../../../core/howto/basics>` in the
Twisted Core documentation for more information on using``twistd`` .



