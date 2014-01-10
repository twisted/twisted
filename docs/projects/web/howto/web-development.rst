
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Web Application Development
===========================






Code layout
-----------



The development of a Twisted Web application should be orthogonal to its
deployment.  This means is that if you are developing a web application, it
should be a resource with children, and internal links.  Some of the children
might use `Nevow <https://launchpad.net/nevow>`_ , some
might be resources manually using ``.write`` , and so on.  Regardless,
the code should be in a Python module, or package, *outside* the web
tree.




You will probably want to test your application as you develop it.  There are
many ways to test, including dropping an ``.rpy`` which looks
like:





.. code-block:: python

    
    from mypackage import toplevel
    resource = toplevel.Resource(file="foo/bar", color="blue")




into a directory, and then running:





.. code-block:: console

    
    % twistd web --path=/directory




You can also write a Python script like:





.. code-block:: python

    
    #!/usr/bin/env python
    
    from twisted.web import server
    from twisted.internet import reactor
    from mypackage import toplevel
    
    reactor.listenTCP(8080,
        server.Site(toplevel.Resource(file="foo/bar", color="blue")))
    reactor.run()





Web application deployment
--------------------------



Which one of these development strategies you use is not terribly important,
since (and this is the important part) deployment is *orthogonal* .
Later, when you want users to actually *use* your code, you should worry
about what to do -- or rather, don't.  Users may have widely different needs.
Some may want to run your code in a different process, so they'll use
distributed web (:api:`twisted.web.distrib <twisted.web.distrib>` ).  Some may be
using the ``twisted-web`` Debian package, and will drop in:





.. code-block:: console

    
    % cat > /etc/local.d/99addmypackage.py
    from mypackage import toplevel
    default.putChild("mypackage", toplevel.Resource(file="foo/bar", color="blue"))
    ^D




If you want to be friendly to your users, you can supply many examples in
your package, like the above ``.rpy`` and the Debian-package drop-in.
But the *ultimate* friendliness is to write a useful resource which does
not have deployment assumptions built in.





Understanding resource scripts (``.rpy``  files)
------------------------------------------------



Twisted Web is not PHP -- it has better tools for organizing code Python
modules and packages, so use them.  In PHP, the only tool for organizing code is
a web page, which leads to silly things like PHP pages full of functions that
other pages import, and so on.  If you were to write your code this way with
Twisted Web, you would do web development using many ``.rpy`` files,
all importing some Python module. This is a *bad idea* -- it mashes
deployment with development, and makes sure your users will be *tied* to
the file-system.




We have ``.rpy`` s because they are useful and necessary.
But using them incorrectly leads to horribly unmaintainable
applications.  The best way to ensure you are using them correctly is
to not use them at all, until you are on your *final* 
deployment stages.  You should then find your ``.rpy`` files
will be less than 10 lines, because you will not *have* more
than 10 lines to write.



