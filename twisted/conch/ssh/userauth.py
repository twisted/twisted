# -*- test-case-name: twisted.conch.test.test_userauth -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of the ssh-userauth service.
Currently implemented authentication types are public-key and password.

Maintainer: Paul Swartz
"""

import struct, warnings
from twisted.conch import error, interfaces
from twisted.conch.ssh import keys, transport, service
from twisted.conch.ssh.common import NS, getNS
from twisted.cred import credentials
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer, reactor
from twisted.python import failure, log



class SSHUserAuthServer(service.SSHService):
    """
    A service implementing the server side of the 'ssh-userauth' service.  It
    is used to authenticate the user on the other side as being able to access
    this server.

    @ivar name: the name of this service: 'ssh-userauth'
    @type name: C{str}
    @ivar authenticatedWith: a list of authentication methods that have
        already been used.
    @type authenticatedWith: C{list}
    @ivar loginTimeout: the number of seconds we wait before disconnecting
        the user for taking too long to authenticate
    @type loginTimeout: C{int}
    @ivar attemptsBeforeDisconnect: the number of failed login attempts we
        allow before disconnecting.
    @type attemptsBeforeDisconnect: C{int}
    @ivar loginAttempts: the number of login attempts that have been made
    @type loginAttempts: C{int}
    @ivar passwordDelay: the number of seconds to delay when the user gives
        an incorrect password
    @type passwordDelay: C{int}
    @ivar interfaceToMethod: a C{dict} mapping credential interfaces to
        authentication methods.  The server checks to see which of the
        cred interfaces have checkers and tells the client that those methods
        are valid for authentication.
    @type interfaceToMethod: C{dict}
    @ivar supportedAuthentications: A list of the supported authentication
        methods.
    @type supportedAuthentications: C{list} of C{str}
    @ivar user: the last username the client tried to authenticate with
    @type user: C{str}
    @ivar method: the current authentication method
    @type method: C{str}
    @ivar nextService: the service the user wants started after authentication
        has been completed.
    @type nextService: C{str}
    @ivar portal: the L{twisted.cred.portal.Portal} we are using for
        authentication
    @type portal: L{twisted.cred.portal.Portal}
    @ivar clock: an object with a callLater method.  Stubbed out for testing.
    """


    name = 'ssh-userauth'
    loginTimeout = 10 * 60 * 60
    # 10 minutes before we disconnect them
    attemptsBeforeDisconnect = 20
    # 20 login attempts before a disconnect
    passwordDelay = 1 # number of seconds to delay on a failed password
    clock = reactor
    interfaceToMethod = {
        credentials.ISSHPrivateKey : 'publickey',
        credentials.IUsernamePassword : 'password',
        credentials.IPluggableAuthenticationModules : 'keyboard-interactive',
    }


    def serviceStarted(self):
        """
        Called when the userauth service is started.  Set up instance
        variables, check if we should allow password/keyboard-interactive
        authentication (only allow if the outgoing connection is encrypted) and
        set up a login timeout.
        """
        self.authenticatedWith = []
        self.loginAttempts = 0
        self.user = None
        self.nextService = None
        self._pamDeferred = None
        self.portal = self.transport.factory.portal

        self.supportedAuthentications = []
        for i in self.portal.listCredentialsInterfaces():
            if i in self.interfaceToMethod:
                self.supportedAuthentications.append(self.interfaceToMethod[i])

        if not self.transport.isEncrypted('in'):
            # don't let us transport password in plaintext
            if 'password' in self.supportedAuthentications:
                self.supportedAuthentications.remove('password')
            if 'keyboard-interactive' in self.supportedAuthentications:
                self.supportedAuthentications.remove('keyboard-interactive')
        self._cancelLoginTimeout = self.clock.callLater(
            self.loginTimeout,
            self.timeoutAuthentication)


    def serviceStopped(self):
        """
        Called when the userauth service is stopped.  Cancel the login timeout
        if it's still going.
        """
        if self._cancelLoginTimeout:
            self._cancelLoginTimeout.cancel()
            self._cancelLoginTimeout = None


    def timeoutAuthentication(self):
        """
        Called when the user has timed out on authentication.  Disconnect
        with a DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE message.
        """
        self._cancelLoginTimeout = None
        self.transport.sendDisconnect(
            transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
            'you took too long')


    def tryAuth(self, kind, user, data):
        """
        Try to authenticate the user with the given method.  Dispatches to a
        auth_* method.

        @param kind: the authentication method to try.
        @type kind: C{str}
        @param user: the username the client is authenticating with.
        @type user: C{str}
        @param data: authentication specific data sent by the client.
        @type data: C{str}
        @return: A Deferred called back if the method succeeded, or erred back
            if it failed.
        @rtype: C{defer.Deferred}
        """
        log.msg('%s trying auth %s' % (user, kind))
        if kind not in self.supportedAuthentications:
            return defer.fail(
                    error.ConchError('unsupported authentication, failing'))
        kind = kind.replace('-', '_')
        f = getattr(self,'auth_%s'%kind, None)
        if f:
            ret = f(data)
            if not ret:
                return defer.fail(
                        error.ConchError('%s return None instead of a Deferred'
                            % kind))
            else:
                return ret
        return defer.fail(error.ConchError('bad auth type: %s' % kind))


    def ssh_USERAUTH_REQUEST(self, packet):
        """
        The client has requested authentication.  Payload::
            string user
            string next service
            string method
            <authentication specific data>

        @type packet: C{str}
        """
        user, nextService, method, rest = getNS(packet, 3)
        if user != self.user or nextService != self.nextService:
            self.authenticatedWith = [] # clear auth state
        self.user = user
        self.nextService = nextService
        self.method = method
        d = self.tryAuth(method, user, rest)
        if not d:
            self._ebBadAuth(
                failure.Failure(error.ConchError('auth returned none')))
            return
        d.addCallback(self._cbFinishedAuth)
        d.addErrback(self._ebMaybeBadAuth)
        d.addErrback(self._ebBadAuth)
        return d


    def _cbFinishedAuth(self, (interface, avatar, logout)):
        """
        The callback when user has successfully been authenticated.  For a
        description of the arguments, see L{twisted.cred.portal.Portal.login}.
        We start the service requested by the user.
        """
        self.transport.avatar = avatar
        self.transport.logoutFunction = logout
        service = self.transport.factory.getService(self.transport,
                self.nextService)
        if not service:
            raise error.ConchError('could not get next service: %s'
                                  % self.nextService)
        log.msg('%s authenticated with %s' % (self.user, self.method))
        self.transport.sendPacket(MSG_USERAUTH_SUCCESS, '')
        self.transport.setService(service())


    def _ebMaybeBadAuth(self, reason):
        """
        An intermediate errback.  If the reason is
        error.NotEnoughAuthentication, we send a MSG_USERAUTH_FAILURE, but
        with the partial success indicator set.

        @type reason: L{twisted.python.failure.Failure}
        """
        reason.trap(error.NotEnoughAuthentication)
        self.transport.sendPacket(MSG_USERAUTH_FAILURE,
                NS(','.join(self.supportedAuthentications)) + '\xff')


    def _ebBadAuth(self, reason):
        """
        The final errback in the authentication chain.  If the reason is
        error.IgnoreAuthentication, we simply return; the authentication
        method has sent its own response.  Otherwise, send a failure message
        and (if the method is not 'none') increment the number of login
        attempts.

        @type reason: L{twisted.python.failure.Failure}
        """
        if reason.check(error.IgnoreAuthentication):
            return
        if self.method != 'none':
            log.msg('%s failed auth %s' % (self.user, self.method))
            if reason.check(UnauthorizedLogin):
                log.msg('unauthorized login: %s' % reason.getErrorMessage())
            elif reason.check(error.ConchError):
                log.msg('reason: %s' % reason.getErrorMessage())
            else:
                log.msg(reason.getTraceback())
            self.loginAttempts += 1
            if self.loginAttempts > self.attemptsBeforeDisconnect:
                self.transport.sendDisconnect(
                        transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                        'too many bad auths')
                return
        self.transport.sendPacket(
                MSG_USERAUTH_FAILURE,
                NS(','.join(self.supportedAuthentications)) + '\x00')


    def auth_publickey(self, packet):
        """
        Public key authentication.  Payload::
            byte has signature
            string algorithm name
            string key blob
            [string signature] (if has signature is True)

        Create a SSHPublicKey credential and verify it using our portal.
        """
        hasSig = ord(packet[0])
        algName, blob, rest = getNS(packet[1:], 2)
        pubKey = keys.Key.fromString(blob)
        signature = hasSig and getNS(rest)[0] or None
        if hasSig:
            b = (NS(self.transport.sessionID) + chr(MSG_USERAUTH_REQUEST) +
                NS(self.user) + NS(self.nextService) + NS('publickey') +
                chr(hasSig) +  NS(pubKey.sshType()) + NS(blob))
            c = credentials.SSHPrivateKey(self.user, algName, blob, b,
                    signature)
            return self.portal.login(c, None, interfaces.IConchUser)
        else:
            c = credentials.SSHPrivateKey(self.user, algName, blob, None, None)
            return self.portal.login(c, None,
                    interfaces.IConchUser).addErrback(self._ebCheckKey,
                            packet[1:])


    def _ebCheckKey(self, reason, packet):
        """
        Called back if the user did not sent a signature.  If reason is
        error.ValidPublicKey then this key is valid for the user to
        authenticate with.  Send MSG_USERAUTH_PK_OK.
        """
        reason.trap(error.ValidPublicKey)
        # if we make it here, it means that the publickey is valid
        self.transport.sendPacket(MSG_USERAUTH_PK_OK, packet)
        return failure.Failure(error.IgnoreAuthentication())


    def auth_password(self, packet):
        """
        Password authentication.  Payload::
            string password

        Make a UsernamePassword credential and verify it with our portal.
        """
        password = getNS(packet[1:])[0]
        c = credentials.UsernamePassword(self.user, password)
        return self.portal.login(c, None, interfaces.IConchUser).addErrback(
                                                        self._ebPassword)


    def _ebPassword(self, f):
        """
        If the password is invalid, wait before sending the failure in order
        to delay brute-force password guessing.
        """
        d = defer.Deferred()
        self.clock.callLater(self.passwordDelay, d.callback, f)
        return d


    def auth_keyboard_interactive(self, packet):
        """
        Keyboard interactive authentication.  No payload.  We create a
        PluggableAuthenticationModules credential and authenticate with our
        portal.
        """
        if self._pamDeferred is not None:
            self.transport.sendDisconnect(
                    transport.DISCONNECT_PROTOCOL_ERROR,
                    "only one keyboard interactive attempt at a time")
            return defer.fail(error.IgnoreAuthentication())
        c = credentials.PluggableAuthenticationModules(self.user,
                self._pamConv)
        return self.portal.login(c, None, interfaces.IConchUser)


    def _pamConv(self, items):
        """
        Convert a list of PAM authentication questions into a
        MSG_USERAUTH_INFO_REQUEST.  Returns a Deferred that will be called
        back when the user has responses to the questions.

        @param items: a list of 2-tuples (message, kind).  We only care about
            kinds 1 (password) and 2 (text).
        @type items: C{list}
        @rtype: L{defer.Deferred}
        """
        resp = []
        for message, kind in items:
            if kind == 1: # password
                resp.append((message, 0))
            elif kind == 2: # text
                resp.append((message, 1))
            elif kind in (3, 4):
                return defer.fail(error.ConchError(
                    'cannot handle PAM 3 or 4 messages'))
            else:
                return defer.fail(error.ConchError(
                    'bad PAM auth kind %i' % kind))
        packet = NS('') + NS('') + NS('')
        packet += struct.pack('>L', len(resp))
        for prompt, echo in resp:
            packet += NS(prompt)
            packet += chr(echo)
        self.transport.sendPacket(MSG_USERAUTH_INFO_REQUEST, packet)
        self._pamDeferred = defer.Deferred()
        return self._pamDeferred


    def ssh_USERAUTH_INFO_RESPONSE(self, packet):
        """
        The user has responded with answers to PAMs authentication questions.
        Parse the packet into a PAM response and callback self._pamDeferred.
        Payload::
            uint32 numer of responses
            string response 1
            ...
            string response n
        """
        d, self._pamDeferred = self._pamDeferred, None

        try:
            resp = []
            numResps = struct.unpack('>L', packet[:4])[0]
            packet = packet[4:]
            while len(resp) < numResps:
                response, packet = getNS(packet)
                resp.append((response, 0))
            if packet:
                raise error.ConchError("%i bytes of extra data" % len(packet))
        except:
            d.errback(failure.Failure())
        else:
            d.callback(resp)



class SSHUserAuthClient(service.SSHService):
    """
    A service implementing the client side of 'ssh-userauth'.

    @ivar name: the name of this service: 'ssh-userauth'
    @type name: C{str}
    @ivar preferredOrder: a list of authentication methods we support, in
        order of preference.  The client will try authentication methods in
        this order, making callbacks for information when necessary.
    @type preferredOrder: C{list}
    @ivar user: the name of the user to authenticate as
    @type user: C{str}
    @ivar instance: the service to start after authentication has finished
    @type instance: L{service.SSHService}
    @ivar authenticatedWith: a list of strings of authentication methods we've tried
    @type authenticatedWith: C{list} of C{str}
    @ivar triedPublicKeys: a list of public key objects that we've tried to
        authenticate with
    @type triedPublicKeys: C{list} of L{Key}
    @ivar lastPublicKey: the last public key object we've tried to authenticate
        with
    @type lastPublicKey: L{Key}
    """


    name = 'ssh-userauth'
    preferredOrder = ['publickey', 'password', 'keyboard-interactive']


    def __init__(self, user, instance):
        self.user = user
        self.instance = instance


    def serviceStarted(self):
        self.authenticatedWith = []
        self.triedPublicKeys = []
        self.lastPublicKey = None
        self.askForAuth('none', '')


    def askForAuth(self, kind, extraData):
        """
        Send a MSG_USERAUTH_REQUEST.

        @param kind: the authentication method to try.
        @type kind: C{str}
        @param extraData: method-specific data to go in the packet
        @type extraData: C{str}
        """
        self.lastAuth = kind
        self.transport.sendPacket(MSG_USERAUTH_REQUEST, NS(self.user) +
                NS(self.instance.name) + NS(kind) + extraData)


    def tryAuth(self, kind):
        """
        Dispatch to an authentication method.

        @param kind: the authentication method
        @type kind: C{str}
        """
        kind = kind.replace('-', '_')
        log.msg('trying to auth with %s' % (kind,))
        f = getattr(self,'auth_%s' % (kind,), None)
        if f:
            return f()


    def _ebAuth(self, ignored, *args):
        """
        Generic callback for a failed authentication attempt.  Respond by
        asking for the list of accepted methods (the 'none' method)
        """
        self.askForAuth('none', '')


    def ssh_USERAUTH_SUCCESS(self, packet):
        """
        We received a MSG_USERAUTH_SUCCESS.  The server has accepted our
        authentication, so start the next service.
        """
        self.transport.setService(self.instance)


    def ssh_USERAUTH_FAILURE(self, packet):
        """
        We received a MSG_USERAUTH_FAILURE.  Payload::
            string methods
            byte partial success

        If partial success is C{True}, then the previous method succeeded but is
        not sufficent for authentication. C{methods} is a comma-separated list
        of accepted authentication methods.

        We sort the list of methods by their position in C{self.preferredOrder},
        removing methods that have already succeeded. We then call
        C{self.tryAuth} with the most preferred method.

        @param packet: the L{MSG_USERAUTH_FAILURE} payload.
        @type packet: C{str}

        @return: a L{defer.Deferred} that will be callbacked with C{None} as
            soon as all authentication methods have been tried, or C{None} if no
            more authentication methods are available.
        @rtype: C{defer.Deferred} or C{None}
        """
        canContinue, partial = getNS(packet)
        partial = ord(partial)
        if partial:
            self.authenticatedWith.append(self.lastAuth)

        def orderByPreference(meth):
            """
            Invoked once per authentication method in order to extract a
            comparison key which is then used for sorting.

            @param meth: the authentication method.
            @type meth: C{str}

            @return: the comparison key for C{meth}.
            @rtype: C{int}
            """
            if meth in self.preferredOrder:
                return self.preferredOrder.index(meth)
            else:
                # put the element at the end of the list.
                return len(self.preferredOrder)

        canContinue = sorted([meth for meth in canContinue.split(',')
                              if meth not in self.authenticatedWith],
                             key=orderByPreference)

        log.msg('can continue with: %s' % canContinue)
        return self._cbUserauthFailure(None, iter(canContinue))


    def _cbUserauthFailure(self, result, iterator):
        if result:
            return
        try:
            method = iterator.next()
        except StopIteration:
            self.transport.sendDisconnect(
                transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                'no more authentication methods available')
        else:
            d = defer.maybeDeferred(self.tryAuth, method)
            d.addCallback(self._cbUserauthFailure, iterator)
            return d


    def ssh_USERAUTH_PK_OK(self, packet):
        """
        This message (number 60) can mean several different messages depending
        on the current authentication type.  We dispatch to individual methods
        in order to handle this request.
        """
        func = getattr(self, 'ssh_USERAUTH_PK_OK_%s' %
                       self.lastAuth.replace('-', '_'), None)
        if func is not None:
            return func(packet)
        else:
            self.askForAuth('none', '')


    def ssh_USERAUTH_PK_OK_publickey(self, packet):
        """
        This is MSG_USERAUTH_PK.  Our public key is valid, so we create a
        signature and try to authenticate with it.
        """
        publicKey = self.lastPublicKey
        b = (NS(self.transport.sessionID) + chr(MSG_USERAUTH_REQUEST) +
             NS(self.user) + NS(self.instance.name) + NS('publickey') +
             '\x01' + NS(publicKey.sshType()) + NS(publicKey.blob()))
        d  = self.signData(publicKey, b)
        if not d:
            self.askForAuth('none', '')
            # this will fail, we'll move on
            return
        d.addCallback(self._cbSignedData)
        d.addErrback(self._ebAuth)


    def ssh_USERAUTH_PK_OK_password(self, packet):
        """
        This is MSG_USERAUTH_PASSWD_CHANGEREQ.  The password given has expired.
        We ask for an old password and a new password, then send both back to
        the server.
        """
        prompt, language, rest = getNS(packet, 2)
        self._oldPass = self._newPass = None
        d = self.getPassword('Old Password: ')
        d = d.addCallbacks(self._setOldPass, self._ebAuth)
        d.addCallback(lambda ignored: self.getPassword(prompt))
        d.addCallbacks(self._setNewPass, self._ebAuth)


    def ssh_USERAUTH_PK_OK_keyboard_interactive(self, packet):
        """
        This is MSG_USERAUTH_INFO_RESPONSE.  The server has sent us the
        questions it wants us to answer, so we ask the user and sent the
        responses.
        """
        name, instruction, lang, data = getNS(packet, 3)
        numPrompts = struct.unpack('!L', data[:4])[0]
        data = data[4:]
        prompts = []
        for i in range(numPrompts):
            prompt, data = getNS(data)
            echo = bool(ord(data[0]))
            data = data[1:]
            prompts.append((prompt, echo))
        d = self.getGenericAnswers(name, instruction, prompts)
        d.addCallback(self._cbGenericAnswers)
        d.addErrback(self._ebAuth)


    def _cbSignedData(self, signedData):
        """
        Called back out of self.signData with the signed data.  Send the
        authentication request with the signature.

        @param signedData: the data signed by the user's private key.
        @type signedData: C{str}
        """
        publicKey = self.lastPublicKey
        self.askForAuth('publickey', '\x01' + NS(publicKey.sshType()) +
                NS(publicKey.blob()) + NS(signedData))


    def _setOldPass(self, op):
        """
        Called back when we are choosing a new password.  Simply store the old
        password for now.

        @param op: the old password as entered by the user
        @type op: C{str}
        """
        self._oldPass = op


    def _setNewPass(self, np):
        """
        Called back when we are choosing a new password.  Get the old password
        and send the authentication message with both.

        @param np: the new password as entered by the user
        @type np: C{str}
        """
        op = self._oldPass
        self._oldPass = None
        self.askForAuth('password', '\xff' + NS(op) + NS(np))


    def _cbGenericAnswers(self, responses):
        """
        Called back when we are finished answering keyboard-interactive
        questions.  Send the info back to the server in a
        MSG_USERAUTH_INFO_RESPONSE.

        @param responses: a list of C{str} responses
        @type responses: C{list}
        """
        data = struct.pack('!L', len(responses))
        for r in responses:
            data += NS(r.encode('UTF8'))
        self.transport.sendPacket(MSG_USERAUTH_INFO_RESPONSE, data)


    def auth_publickey(self):
        """
        Try to authenticate with a public key.  Ask the user for a public key;
        if the user has one, send the request to the server and return True.
        Otherwise, return False.

        @rtype: C{bool}
        """
        d = defer.maybeDeferred(self.getPublicKey)
        d.addBoth(self._cbGetPublicKey)
        return d


    def _cbGetPublicKey(self, publicKey):
        if isinstance(publicKey, str):
            warnings.warn("Returning a string from "
                          "SSHUserAuthClient.getPublicKey() is deprecated "
                          "since Twisted 9.0.  Return a keys.Key() instead.",
                          DeprecationWarning)
            publicKey = keys.Key.fromString(publicKey)
        if not isinstance(publicKey, keys.Key): # failure or None
            publicKey = None
        if publicKey is not None:
            self.lastPublicKey = publicKey
            self.triedPublicKeys.append(publicKey)
            log.msg('using key of type %s' % publicKey.type())
            self.askForAuth('publickey', '\x00' + NS(publicKey.sshType()) +
                            NS(publicKey.blob()))
            return True
        else:
            return False


    def auth_password(self):
        """
        Try to authenticate with a password.  Ask the user for a password.
        If the user will return a password, return True.  Otherwise, return
        False.

        @rtype: C{bool}
        """
        d = self.getPassword()
        if d:
            d.addCallbacks(self._cbPassword, self._ebAuth)
            return True
        else: # returned None, don't do password auth
            return False


    def auth_keyboard_interactive(self):
        """
        Try to authenticate with keyboard-interactive authentication.  Send
        the request to the server and return True.

        @rtype: C{bool}
        """
        log.msg('authing with keyboard-interactive')
        self.askForAuth('keyboard-interactive', NS('') + NS(''))
        return True


    def _cbPassword(self, password):
        """
        Called back when the user gives a password.  Send the request to the
        server.

        @param password: the password the user entered
        @type password: C{str}
        """
        self.askForAuth('password', '\x00' + NS(password))


    def signData(self, publicKey, signData):
        """
        Sign the given data with the given public key.

        By default, this will call getPrivateKey to get the private key,
        then sign the data using Key.sign().

        This method is factored out so that it can be overridden to use
        alternate methods, such as a key agent.

        @param publicKey: The public key object returned from L{getPublicKey}
        @type publicKey: L{keys.Key}

        @param signData: the data to be signed by the private key.
        @type signData: C{str}
        @return: a Deferred that's called back with the signature
        @rtype: L{defer.Deferred}
        """
        key = self.getPrivateKey()
        if not key:
            return
        return key.addCallback(self._cbSignData, signData)


    def _cbSignData(self, privateKey, signData):
        """
        Called back when the private key is returned.  Sign the data and
        return the signature.

        @param privateKey: the private key object
        @type publicKey: L{keys.Key}
        @param signData: the data to be signed by the private key.
        @type signData: C{str}
        @return: the signature
        @rtype: C{str}
        """
        if not isinstance(privateKey, keys.Key):
            warnings.warn("Returning a PyCrypto key object from "
                          "SSHUserAuthClient.getPrivateKey() is deprecated "
                          "since Twisted 9.0.  Return a keys.Key() instead.",
                          DeprecationWarning)
            privateKey = keys.Key(privateKey)
        return privateKey.sign(signData)


    def getPublicKey(self):
        """
        Return a public key for the user.  If no more public keys are
        available, return C{None}.

        This implementation always returns C{None}.  Override it in a
        subclass to actually find and return a public key object.

        @rtype: L{Key} or L{NoneType}
        """
        return None


    def getPrivateKey(self):
        """
        Return a L{Deferred} that will be called back with the private key
        object corresponding to the last public key from getPublicKey().
        If the private key is not available, errback on the Deferred.

        @rtype: L{Deferred} called back with L{Key}
        """
        return defer.fail(NotImplementedError())


    def getPassword(self, prompt = None):
        """
        Return a L{Deferred} that will be called back with a password.
        prompt is a string to display for the password, or None for a generic
        'user@hostname's password: '.

        @type prompt: C{str}/C{None}
        @rtype: L{defer.Deferred}
        """
        return defer.fail(NotImplementedError())


    def getGenericAnswers(self, name, instruction, prompts):
        """
        Returns a L{Deferred} with the responses to the promopts.

        @param name: The name of the authentication currently in progress.
        @param instruction: Describes what the authentication wants.
        @param prompts: A list of (prompt, echo) pairs, where prompt is a
        string to display and echo is a boolean indicating whether the
        user's response should be echoed as they type it.
        """
        return defer.fail(NotImplementedError())


MSG_USERAUTH_REQUEST          = 50
MSG_USERAUTH_FAILURE          = 51
MSG_USERAUTH_SUCCESS          = 52
MSG_USERAUTH_BANNER           = 53
MSG_USERAUTH_INFO_RESPONSE    = 61
MSG_USERAUTH_PK_OK            = 60

messages = {}
for k, v in locals().items():
    if k[:4]=='MSG_':
        messages[v] = k

SSHUserAuthServer.protocolMessages = messages
SSHUserAuthClient.protocolMessages = messages
del messages
del v

# Doubles, not included in the protocols' mappings
MSG_USERAUTH_PASSWD_CHANGEREQ = 60
MSG_USERAUTH_INFO_REQUEST     = 60
