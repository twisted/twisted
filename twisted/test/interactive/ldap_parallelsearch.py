#!/usr/bin/python2
from twisted.protocols import ldap, pureber
from twisted.internet import tcp
import twisted.internet.main

class LDAPSearchAndPrint(ldap.LDAPSearch):
    def __init__(self, ldapclient, prefix):
        ldap.LDAPSearch.__init__(self, ldapclient,
                                 baseObject='dc=example, dc=com')
        self.prefix=prefix

    def handle_success(self):
        self.ldapclient.search_done(self.prefix)

    def handle_entry(self, objectName, attributes):
        print "%s: %s %s"%(self.prefix, objectName,
                           repr(map(lambda (a,l):
                                    (str(a),
                                     map(lambda i, l=l: str(i), l)),
                                    attributes)))

    def handle_fail(self, resultCode, errorMessage):
        print "%s: fail: %d: %s"%(self.prefix, resultCode, errorMessage or "Unknown error")
        self.ldapclient.search_done(self.prefix)

class SearchALot(ldap.LDAPClient):
    clients = map(str, xrange(0,20))
    
    def connectionMade(self):
        self.bind()

    def handle_bind_success(self, matchedDN, serverSaslCreds):
        for k in self.clients:
            LDAPSearchAndPrint(self, k)

    def search_done(self, prefix):
        self.clients.remove(prefix)
        if self.clients==[]:
            twisted.internet.main.shutDown()

def main():
    tcp.Client("localhost", 389, SearchALot())
    twisted.internet.main.run()

if __name__ == "__main__":
    main()
