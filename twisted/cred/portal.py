
from twisted.internet import defer
from twisted.internet.defer import maybeDeferred
from twisted.python import failure, reflect, components
from twisted.cred import error

class IRealm(components.Interface):
    def requestAvatar(self, avatarId, mind, *interfaces):
        pass

class Portal:
    def __init__(self, realm):
        """
        """
        self.realm = realm
        self.checkers = {}

    def registerChecker(self, checker, *credentialInterfaces):
        if not credentialInterfaces:
            credentialInterfaces = checker.credentialInterfaces
        for credentialInterface in credentialInterfaces:
            self.checkers[credentialInterface] = checker

    def login(self, credentials, mind, *interfaces):
        """
        
        @param credentials: an implementor of
        twisted.cred.interfaces.ICredentials

        @param mind: an object which implements a client-side interface for
        your particular realm.  In many cases, this may be None, so if the word
        'mind' confuses you, just ignore it.

        @param interfaces: list of interfaces for the perspective that the mind
        wishes to attach to.  Usually, this will be only one interface, for
        example IMailAccount.  For highly dynamic protocols, however, this may
        be a list like (IMailAccount, IUserChooser, IServiceInfo).  To expand:
        if we are speaking to the system over IMAP, any information that will
        be relayed to the user MUST be returned as an IMailAccount implementor;
        IMAP clients would not be able to understand anything else.  Any
        information about unusual status would have to be relayed as a single
        mail message in an otherwise-empty mailbox.  However, in a web-based
        mail system, or a PB-based client, the ``mind'' object inside the web
        server (implemented with a dynamic page-viewing mechanism such as
        woven) or on the user's client program may be intelligent enough to
        respond to several ``server''-side interfaces.

        @return: A deferred which will fire a tuple of (interface,
        avatarAspect, logout).  The interface will be one of the interfaces
        passed in the 'interfaces' argument.  The 'avatarAspect' will implement
        that interface.  The 'logout' object is a callable which will detach
        the mind from the avatar.  It must be called when the user has
        conceptually disconnected from the service.  Although in some cases
        this will not be in connectionLost (such as in a web-based session), it
        will always be at the end of a user's interactive session.
        """
        ifac = components.getInterfaces(credentials)
        for i in ifac:
            c = self.checkers.get(i)
            if c is not None:
                return maybeDeferred(c.requestAvatarId, credentials
                    ).addCallback(self.realm.requestAvatar, mind, *interfaces
                    )
        return defer.fail(failure.Failure(error.UnhandledCredentials(
            "No checker for %s" % ' ,'.join(map(reflect.qual, ifac)))))

