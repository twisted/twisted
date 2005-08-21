
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

pubkey = keys.getPublicKeyString(
    '%s/ssh_host_dsa_key.pub' % sshkeys)
privkey = keys.getPrivateKeyObject(
    '%s/ssh_host_dsa_key' % sshkeys)

class SSHFactory(factory.SSHFactory):
    publicKeys = {common.getNS(pubkey)[0]: pubkey}
    privateKeys = {keys.objectType(privkey): privkey}

t = SSHFactory()
t.portal = p

application = service.Application('WELSHSERVER')
internet.TCPServer( 5822, t,).setServiceParent(application)

