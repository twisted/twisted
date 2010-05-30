# You can run this .tac file directly with:
#    twistd -ny welsh.tac

from twisted.application import service, internet
from twisted.conch.ssh import factory, keys, common
from twisted.cred import portal

from welsh import WelshChecker, WelshRealm

passwd  = './welshpasswd'
conf    = './welsh.conf'
sshkeys = '../sshkeys'
port    = 5822

p = portal.Portal(WelshRealm(conf))
p.registerChecker(WelshChecker(passwd))

pubkey = keys.Key.fromFile(
	'%s/ssh_host_dsa_key.pub' % sshkeys).blob()
privkey = keys.Key.fromFile(
    '%s/ssh_host_dsa_key' % sshkeys).keyObject

class SSHFactory(factory.SSHFactory):
    publicKeys = {common.getNS(pubkey)[0]: pubkey}
    privateKeys = {keys.objectType(privkey): privkey}

t = SSHFactory()
t.portal = p

application = service.Application('WELSHSERVER')
internet.TCPServer( 5822, t,).setServiceParent(application)

