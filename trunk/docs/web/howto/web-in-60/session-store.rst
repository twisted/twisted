
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Storing Objects in the Session
==============================





This example shows you how you can persist objects across requests in the
session object.




As was discussed :doc:`previously <session-basics>` , instances
of :api:`twisted.web.server.Session <Session>` last as long as
the notional session itself does. Each time :api:`twisted.web.server.Request.getSession <Request.getSession>` is called, if the session
for the request is still active, then the same ``Session`` instance is
returned as was returned previously. Because of this, ``Session`` 
instances can be used to keep other objects around for as long as the session
exists.




It's easier to demonstrate how this works than explain it, so here's an
example:





.. code-block:: console

    
    >>> from zope.interface import Interface, Attribute, implements
    >>> from twisted.python.components import registerAdapter
    >>> from twisted.web.server import Session
    >>> class ICounter(Interface):
    ...     value = Attribute("An int value which counts up once per page view.")
    ...
    >>> class Counter(object):
    ...     implements(ICounter)
    ...     def __init__(self, session):
    ...         self.value = 0
    ...
    >>> registerAdapter(Counter, Session, ICounter)
    >>> ses = Session(None, None)
    >>> data = ICounter(ses)
    >>> print data
    <__main__.Counter object at 0x8d535ec>
    >>> print data is ICounter(ses)
    True
    >>>




*What?* , I hear you say.




What's shown in this example is the interface and adaption-based
API which ``Session`` exposes for persisting state. There are
several critical pieces interacting here:






- ``ICounter`` is an interface which serves several purposes. Like
  all interfaces, it documents the API of some class of objects (in this case,
  just the ``value`` attribute). It also serves as a key into what is
  basically a dictionary within the session object: the interface is used to
  store or retrieve a value on the session (the ``Counter`` instance,
  in this case).
- ``Counter`` is the class which actually holds the session data in
  this example. It implements ``ICounter`` (again, mostly for
  documentation purposes). It also has a ``value`` attribute, as the
  interface declared.
- The :api:`twisted.python.components.registerAdapter <registerAdapter>` call sets up the
  relationship between its three arguments so that adaption will do what we
  want in this case.
- Adaption is performed by the expression ``ICounter(ses)`` . This
  is read as : adapt ``ses`` to ``ICounter`` . Because
  of the ``registerAdapter`` call, it is roughly equivalent
  to ``Counter(ses)`` . However (because of certain
  things ``Session`` does), it also saves the ``Counter`` 
  instance created so that it will be returned the next time this adaption is
  done. This is why the last statement produces ``True`` .





If you're still not clear on some of the details there, don't worry about it
and just remember this: ``ICounter(ses)`` gives you an object you can
persist state on. It can be as much or as little state as you want, and you can
use as few or as many different ``Interface`` classes as you want on a
single ``Session`` instance.




With those conceptual dependencies out of the way, it's a very short step to
actually getting persistent state into a Twisted Web application. Here's an
example which implements a simple counter, re-using the definitions from the
example above:





.. code-block:: python

    
    from twisted.web.resource import Resource
    
    class CounterResource(Resource):
        def render_GET(self, request):
            session = request.getSession()
            counter = ICounter(session)
            counter.value += 1
            return "Visit #%d for you!" % (counter.value,)




Pretty simple from this side, eh? All this does is
use ``Request.getSession`` and the adaption from above, plus some
integer math to give you a session-based visit counter.




Here's the complete source for an :doc:`rpy script <rpy-scripts>` 
based on this example:





.. code-block:: python

    
    cache()
    
    from zope.interface import Interface, Attribute, implements
    from twisted.python.components import registerAdapter
    from twisted.web.server import Session
    from twisted.web.resource import Resource
    
    class ICounter(Interface):
        value = Attribute("An int value which counts up once per page view.")
    
    class Counter(object):
        implements(ICounter)
        def __init__(self, session):
            self.value = 0
    
    registerAdapter(Counter, Session, ICounter)
    
    class CounterResource(Resource):
        def render_GET(self, request):
            session = request.getSession()
            counter = ICounter(session)
            counter.value += 1
            return "Visit #%d for you!" % (counter.value,)
    
    resource = CounterResource()




One more thing to note is the ``cache()`` call at the top
of this example. As with the :doc:`previous example <http-auth>` where this came up, this rpy script is stateful. This
time, it's the ``ICounter`` definition and
the ``registerAdapter`` call that need to be executed only
once. If we didn't use ``cache`` , every request would define
a new, different interface named ``ICounter`` . Each of these
would be a different key in the session, so the counter would never
get past one.



