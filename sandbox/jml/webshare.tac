from twisted.application import internet, service
from twisted.web import static
from nevow import rend, tags as T, appserver
import win32goodies

class WebShare(rend.Page):
    def __init__(self):
        rend.Page.__init__(self)

    def getDynamicChild(self, name, request):
        shares = win32goodies.getSystemShares()
        path = shares.get(name, None)
        if path is not None:
            return static.File(path)

    def allShares(self):
        shares = win32goodies.getSystemShares().keys()
        return T.ul[[ T.li[T.a(href=share)[share]] for share in shares ]]

    def thisBox(self):
        import socket
        return socket.gethostname()

    docFactory = rend.stan(T.html[ T.head[ T.title[ 'Web Shares' ] ],
                                   T.body[ T.h1[ thisBox ],
                                           T.h2[ 'Web Shares' ],
                                           allShares ] ])


application = service.Application('webshare')
internet.TCPServer(
    8080, appserver.NevowSite(WebShare())
).setServiceParent(application)
    
