
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Session Basics
==============





Sessions are the most complicated topic covered in this series of examples,
and because of that it is going to take a few examples to cover all of the
different aspects. This first example demonstrates the very basics of the
Twisted Web session API: how to get the session object for the current request
and how to prematurely expire a session.




Before diving into the APIs, let's look at the big picture of
sessions in Twisted Web. Sessions are represented by instances
of :api:`twisted.web.server.Session <Session>` . The :api:`twisted.web.server.Site <Site>` creates a new instance
of ``Session`` the first time an application asks for it for
a particular session. ``Session`` instances are kept on
the ``Site`` instance until they expire (due to inactivity or
because they are explicitly expired). Each time after the first that a
particular session's ``Session`` object is requested, it is
retrieved from the ``Site`` .




With the conceptual underpinnings of the upcoming API in place, here comes
the example. This will be a very simple :doc:`rpy script <rpy-scripts>` which tells a user what its unique session identifier is and lets it
prematurely expire the session.




First, we'll import :api:`twisted.web.resource.Resource <Resource>` so we can define a couple of
subclasses of it:





.. code-block:: python

    
    from twisted.web.resource import Resource




Next we'll define the resource which tells the client what its session
identifier is. This is done easily by first getting the session object
using :api:`twisted.web.server.Request.getSession <Request.getSession>` and
then getting the session object's uid attribute:





.. code-block:: python

    
    class ShowSession(Resource):
        def render_GET(self, request):
            return 'Your session id is: ' + request.getSession().uid




To let the client expire its own session before it times out, we'll define
another resource which expires whatever session it is requested with. This is
done using the :api:`twisted.web.server.Session.expire <Session.expire>` 
method:





.. code-block:: python

    
    class ExpireSession(Resource):
        def render_GET(self, request):
            request.getSession().expire()
            return 'Your session has been expired.'




Finally, to make the example an rpy script, we'll make an instance
of ``ShowSession`` and give it an instance
of ``ExpireSession`` as a child using :api:`twisted.web.resource.Resource.putChild <Resource.putChild>` :





.. code-block:: python

    
    resource = ShowSession()
    resource.putChild("expire", ExpireSession())




And that is the complete example. You can fire this up and load the top
page. You'll see a (rather opaque) session identifier that remains the same
across reloads (at least until you flush the ``TWISTED_SESSION`` cookie
from your browser or enough time passes). You can then visit
the ``expire`` child and go back to the top page and see that you have
a new session.




Here's the complete source for the example:





.. code-block:: python

    
    from twisted.web.resource import Resource
    
    class ShowSession(Resource):
        def render_GET(self, request):
            return 'Your session id is: ' + request.getSession().uid
    
    class ExpireSession(Resource):
        def render_GET(self, request):
            request.getSession().expire()
            return 'Your session has been expired.'
    
    resource = ShowSession()
    resource.putChild("expire", ExpireSession())



