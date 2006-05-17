from twisted.web2 import channel, resource, http, responsecode, server

class ProtectedResource(resource.Resource):
    def render(self, req):
        return http.Response(responsecode.OK, 
                             stream=("Hello, you've successfully accessed "
                                     "a protected resource."))

from twisted.web2.auth import digest, basic, wrapper

from twisted.cred.portal import Portal
from twisted.cred import checkers

import credsetup

portal = Portal(credsetup.HTTPAuthRealm())

checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(guest='guest123')

portal.registerChecker(checker)

root = wrapper.HTTPAuthResource(ProtectedResource(),
                                (digest.DigestCredentialFactory('md5', 
                                                               'My Realm'),),
                                portal, (credsetup.IHTTPUser,))

site = server.Site(root)

# Start up the server
from twisted.application import service, strports
application = service.Application("HTTP Auth Demo")
s = strports.service('tcp:8080', channel.HTTPFactory(site))
s.setServiceParent(application)

            
