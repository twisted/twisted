
import sys
from twisted.python import log
log.startLogging(sys.stdout)

from twisted.spread import pb
from twisted.internet import reactor
from twisted.cred import credentials
import pbold
import jelliers

def cbGetServer(port, avatar):
    print port

def ebGetServer(failure):
    log.err(failure)

def cbServerList(lst, avatar):
    return avatar.callRemote('getServer', lst.pop()
        ).addCallback(cbGetServer, avatar
        ).addErrback(ebGetServer
        )

def ebServerList(failure):
    log.err(failure)

def cbMigrate(avatar):
    return avatar.callRemote('getServerList'
        ).addCallback(cbServerList, avatar
        ).addErrback(ebServerList
        )

def ebMigrate(failure):
    log.err(failure)

def main():
    client = pb.PBClientFactory()
    reactor.connectUNIX('migrate', client)
    client.login(credentials.UsernamePassword('user', 'pass')
        ).addCallbacks(cbMigrate, ebMigrate
        ).addBoth(lambda _: reactor.stop()
        )
    reactor.run()

if __name__ == '__main__':
    main()
