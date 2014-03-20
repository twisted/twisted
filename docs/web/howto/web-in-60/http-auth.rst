
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

HTTP Authentication
===================





Many of the previous examples have looked at how to serve content by using
existing resource classes or implementing new ones. In this example we'll use
Twisted Web's basic or digest HTTP authentication to control access to these
resources.




:api:`twisted.web.guard <guard>` , the Twisted Web
module which provides most of the APIs that will be used in this
example, helps you to
add `authentication <http://en.wikipedia.org/wiki/Authentication>`_ 
and `authorization <http://en.wikipedia.org/wiki/Authorization>`_ 
to a resource hierarchy. It does this by providing a resource which
implements :api:`twisted.web.resource.Resource.getChild <getChild>` to return
a :doc:`dynamically selected resource <dynamic-dispatch>` . The selection is based on the authentication headers in
the request. If those headers indicate that the request is made on
behalf of Alice, then Alice's resource will be returned. If they
indicate that it was made on behalf of Bob, his will be returned. If
the headers contain invalid credentials, an error resource is
returned. Whatever happens, once this resource is returned, URL
traversal continues as normal from that resource.




The resource that implements this is :api:`twisted.web.guard.HTTPAuthSessionWrapper <HTTPAuthSessionWrapper>` , though it is directly
responsible for very little of the process. It will extract headers from the
request and hand them off to a credentials factory to parse them according to
the appropriate standards (eg `HTTPAuthentication: Basic and Digest Access Authentication <http://tools.ietf.org/html/rfc2617>`_ ) and then hand the
resulting credentials object off to a :api:`twisted.cred.portal.Portal <Portal>` , the core
of :doc:`Twisted Cred <../../../core/howto/cred>` , a system for
uniform handling of authentication and authorization. We won't discuss Twisted
Cred in much depth here. To make use of it with Twisted Web, the only thing you
really need to know is how to implement an :api:`twisted.cred.portal.IRealm <IRealm>` .




You need to implement a realm because the realm is the object that
actually decides which resources are used for which users. This can be
as complex or as simple as it suitable for your application. For this
example we'll keep it very simple: each user will have a resource
which is a static file listing of the ``public_html`` 
directory in their UNIX home directory. First, we need to
import ``implements`` from ``zope.interface`` 
and ``IRealm`` 
from ``twisted.cred.portal`` . Together these will let me mark
this class as a realm (this is mostly - but not entirely - a
documentation thing). We'll also need :api:`twisted.web.static.File <File>` for the actual implementation
later.





.. code-block:: python

    
    from zope.interface import implements
    
    from twisted.cred.portal import IRealm
    from twisted.web.static import File
    
    class PublicHTMLRealm(object):
        implements(IRealm)




A realm only needs to implement one method: :api:`twisted.cred.portal.IRealm.requestAvatar <requestAvatar>` . This method is called
after any successful authentication attempt (ie, Alice supplied the right
password). Its job is to return the *avatar* for the user who succeeded in
authenticating. An *avatar* is just an object that represents a user. In
this case, it will be a ``File`` . In general, with ``Guard`` ,
the avatar must be a resource of some sort.





.. code-block:: python

    
    ...
        def requestAvatar(self, avatarId, mind, *interfaces):
            if IResource in interfaces:
                return (IResource, File("/home/%s/public_html" % (avatarId,)), lambda: None)
            raise NotImplementedError()




A few notes on this method:





- The ``avatarId`` parameter is essentially the username. It's the
  job of some other code to extract the username from the request headers and
  make sure it gets passed here.
- The ``mind`` is always ``None`` when writing a realm to
  be used with ``Guard`` . You can ignore it until you want to write a
  realm for something else.
- ``Guard`` is always
  passed ``IResource`` as
  the ``interfaces`` parameter. If ``interfaces`` only
  contains interfaces your code doesn't understand,
  raising ``NotImplementedError`` is the thing to do, as
  above. You'll only need to worry about getting a different interface when
  you write a realm for something other than ``Guard`` .
- If you want to track when a user logs out, that's what the last element of
  the returned tuple is for. It will be called when this avatar logs
  out. ``lambda: None`` is the idiomatic no-op logout function.
- Notice that the path handling code in this example is written very
  poorly. This example may be vulnerable to certain unintentional information
  disclosure attacks. This sort of problem is exactly the
  reason :api:`twisted.python.filepath.FilePath <FilePath>` 
  exists. However, that's an example for another day...





We're almost ready to set up the resource for this example. To
create an ``HTTPAuthSessionWrapper`` , though, we need two
things. First, a portal, which requires the realm above, plus at least
one credentials checker:





.. code-block:: python

    
    from twisted.cred.portal import Portal
    from twisted.cred.checkers import FilePasswordDB
    
    portal = Portal(PublicHTMLRealm(), [FilePasswordDB('httpd.password')])




:api:`twisted.cred.checkers.FilePasswordDB <FilePasswordDB>` is the
credentials checker. It knows how to read ``passwd(5)`` -style (loosely)
files to check credentials against. It is responsible for the authentication
work after ``HTTPAuthSessionWrapper`` extracts the credentials from the
request.




Next we need either :api:`twisted.web.guard.BasicCredentialFactory <BasicCredentialFactory>` 
or :api:`twisted.web.guard.DigestCredentialFactory <DigestCredentialFactory>` . The former
knows how to challenge HTTP clients to do basic authentication; the
latter, digest authentication. We'll use digest here:





.. code-block:: python

    
    from twisted.web.guard import DigestCredentialFactory
    
    credentialFactory = DigestCredentialFactory("md5", "example.org")




The two parameters to this constructor are the hash algorithm and
the HTTP authentication realm which will be used. The only other valid
hash algorithm is "sha" (but be careful, MD5 is more widely supported
than SHA). The HTTP authentication realm is mostly just a string that
is presented to the user to let them know why they're authenticating
(you can read more about this in
the `RFC <http://tools.ietf.org/html/rfc2617>`_ ).




With those things created, we can finally
instantiate ``HTTPAuthSessionWrapper`` :





.. code-block:: python

    
    from twisted.web.guard import HTTPAuthSessionWrapper
    
    resource = HTTPAuthSessionWrapper(portal, [credentialFactory])




There's just one last thing that needs to be done
here. When :doc:`rpy scripts <rpy-scripts>` were
introduced, it was mentioned that they are evaluated in an unusual
context. This is the first example that actually needs to take this
into account. It so happens that ``DigestCredentialFactory`` 
instances are stateful. Authentication will only succeed if the same
instance is used to both generate challenges and examine the responses
to those challenges. However, the normal mode of operation for an rpy
script is for it to be re-executed for every request. This leads to a
new ``DigestCredentialFactory`` being created for every request, preventing
any authentication attempt from ever succeeding.




There are two ways to deal with this. First, and the better of the two ways,
we could move almost all of the code into a real Python module, including the
code that instantiates the ``DigestCredentialFactory`` . This would
ensure that the same instance was used for every request. Second, and the easier
of the two ways, we could add a call to ``cache()`` to the beginning of
the rpy script:





.. code-block:: python

    
    cache()




``cache`` is part of the globals of any rpy script, so you don't
need to import it (it's okay to be cringing at this
point). Calling ``cache`` makes Twisted re-use the result of the first
evaluation of the rpy script for subsequent requests too - just what we want in
this case.




Here's the complete example (with imports re-arranged to the more
conventional style):





.. code-block:: python

    
    cache()
    
    from zope.interface import implements
    
    from twisted.cred.portal import IRealm, Portal
    from twisted.cred.checkers import FilePasswordDB
    from twisted.web.static import File
    from twisted.web.resource import IResource
    from twisted.web.guard import HTTPAuthSessionWrapper, DigestCredentialFactory
    
    class PublicHTMLRealm(object):
        implements(IRealm)
    
        def requestAvatar(self, avatarId, mind, *interfaces):
            if IResource in interfaces:
                return (IResource, File("/home/%s/public_html" % (avatarId,)), lambda: None)
            raise NotImplementedError()
    
    portal = Portal(PublicHTMLRealm(), [FilePasswordDB('httpd.password')])
    
    credentialFactory = DigestCredentialFactory("md5", "localhost:8080")
    resource = HTTPAuthSessionWrapper(portal, [credentialFactory])




And voila, a password-protected per-user Twisted Web server.



