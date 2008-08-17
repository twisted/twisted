# You can run this .tac file directly with:
#    twistd -ny httpauth.tac

from twisted.web2 import channel, resource, http, responsecode, server
from twisted.web2.auth.interfaces import IAuthenticatedRequest, IHTTPUser

class ProtectedResource(resource.Resource):
    """
    A resource that is protected by HTTP Auth
    """
    addSlash = True

    def render(self, req):
        """
        I adapt C{req} to an L{IAuthenticatedRequest} before using the
        avatar to return a personalized message.
        """
        avatar = IAuthenticatedRequest(req).avatar

        return http.Response(
            responsecode.OK,
            stream=("Hello %s, you've successfully accessed "
                    "a protected resource." % (avatar.username,)))

from twisted.web2.auth import digest, basic, wrapper

from twisted.cred.portal import Portal
from twisted.cred import checkers

import credsetup

#
# Create the portal with our realm that knows about the kind of avatar
# we want.
#

portal = Portal(credsetup.HTTPAuthRealm())

#
# Create a checker that knows about the type of backend we want to use
# and that knows about the ICredentials we get back from our
# ICredentialFactories.  And tell our portal to use it.
#

checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(guest='guest123')

portal.registerChecker(checker)

#
# Set up our HTTPAuthResource, we have to tell it the root of the resource
# heirarchy we want to protect, as well as the credential factories we want
# to support, the portal we want to use for logging in, and the interfaces
# that IAuthenticatedRequest.avatar to may implement.
#

root = wrapper.HTTPAuthResource(ProtectedResource(),
                                (basic.BasicCredentialFactory('My Realm'),
                                 digest.DigestCredentialFactory('md5',
                                                               'My Realm')),
                                portal, (IHTTPUser,))

site = server.Site(root)

# Start up the server
from twisted.application import service, strports
application = service.Application("HTTP Auth Demo")
s = strports.service('tcp:8080', channel.HTTPFactory(site))
s.setServiceParent(application)


