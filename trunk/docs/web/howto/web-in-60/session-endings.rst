
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Session Endings
===============





The previous two examples introduced Twisted Web's session APIs. This
included accessing the session object, storing state on it, and retrieving it
later, as well as the idea that the :api:`twisted.web.server.Session <Session>` object has a lifetime which is tied to
the notional session it represents. This example demonstrates how to exert some
control over that lifetime and react when it expires.




The lifetime of a session is controlled by the ``sessionTimeout`` 
attribute of the ``Session`` class. This attribute gives the number of
seconds a session may go without being accessed before it expires. The default
is 15 minutes. In this example we'll change that to a different value.




One way to override the value is with a subclass:





.. code-block:: python

    
    from twisted.web.server import Session
    
    class ShortSession(Session):
        sessionTimeout = 60




To have Twisted Web actually make use of this session class, rather
than the default, it is also necessary to override
the ``sessionFactory`` attribute of :api:`twisted.web.server.Site <Site>` . We could do this with another
subclass, but we could also do it to just one instance
of ``Site`` :





.. code-block:: python

    
    from twisted.web.server import Site
    
    factory = Site(rootResource)
    factory.sessionFactory = ShortSession




Sessions given out for requests served by this ``Site`` will
use ``ShortSession`` and only last one minute without activity.




You can have arbitrary functions run when sessions expire,
too. This can be useful for cleaning up external resources associated
with the session, tracking usage statistics, and more. This
functionality is provided via :api:`twisted.web.server.Session.notifyOnExpire <Session.notifyOnExpire>` . It accepts a
single argument: a function to call when the session expires. Here's a
trivial example which prints a message whenever a session expires:





.. code-block:: python

    
    from twisted.web.resource import Resource
    
    class ExpirationLogger(Resource):
        sessions = set()
    
        def render_GET(self, request):
            session = request.getSession()
            if session.uid not in self.sessions:
                self.sessions.add(session.uid)
                session.notifyOnExpire(lambda: self._expired(session.uid))
            return ""
    
        def _expired(self, uid):
            print "Session", uid, "has expired."
            self.sessions.remove(uid)




Keep in mind that using a method as the callback will keep the instance (in
this case, the ``ExpirationLogger`` resource) in memory until the
session expires.




With those pieces in hand, here's an example that prints a message whenever a
session expires, and uses sessions which last for 5 seconds:





.. code-block:: python

    
    from twisted.web.server import Site, Session
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    class ShortSession(Session):
        sessionTimeout = 5
    
    class ExpirationLogger(Resource):
        sessions = set()
    
        def render_GET(self, request):
            session = request.getSession()
            if session.uid not in self.sessions:
                self.sessions.add(session.uid)
                session.notifyOnExpire(lambda: self._expired(session.uid))
            return ""
    
        def _expired(self, uid):
            print "Session", uid, "has expired."
            self.sessions.remove(uid)
    
    rootResource = Resource()
    rootResource.putChild("logme", ExpirationLogger())
    factory = Site(rootResource)
    factory.sessionFactory = ShortSession
    
    reactor.listenTCP(8080, factory)
    reactor.run()




Since ``Site`` customization is required, this example can't be
rpy-based, so it brings back the manual ``reactor.listenTCP`` 
and ``reactor.run`` calls. Run it and visit ``/logme`` to see
it in action. Keep visiting it to keep your session active. Stop visiting it for
five seconds to see your session expiration message.



