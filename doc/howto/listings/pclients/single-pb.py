from twisted.cred import error
from twisted.spread import pb

class PerspectiveInUse(error.Unauthorized):
    """Raised when a client requests a perspective already connected to another.
    """
    # XXX: Is there any information this exception should carry, i.e.
    #   the Perspective in question.
    #   the client it's currently attached to.
    #   the Identity which attached it.


class SingleClientPerspective_PB(pb.Perspective):
    """One client may attach to me at a time.

    With verbose logging and some detection for lost connections.
    """

    client = None

    # This example is from cvstoys.actions.pb.Notifiee.

    def brokerAttached(self, ref, identity, broker):
        log.msg("%(identityName)s<auth%(authID)X>@"
                "%(peer)s<broker%(brokerID)X> "
                "requests attaching client %(client)s to "
                "%(perspectiveName)s@%(serviceName)s" %
                {'identityName': identity.name,
                 'authID': id(identity.authorizer),
                 'peer': broker.transport.getPeer(),
                 'brokerID': id(broker),
                 'client': ref,
                 'perspectiveName': self.getPerspectiveName(),
                 'serviceName': self.service.getServiceName(),
                 })

        if self.client:
            oldclient, oldid, oldbroker = self.client
            if oldbroker:
                brokerstr = "<broker%X>" % (id(oldbroker),)
            else:
                brokerstr = "<no broker>"
            log.msg(
                "%(pn)s@%(sn)s already has client %(client)s "
                "from %(id)s@%(broker)s" %
                {'pn': self.getPerspectiveName(),
                 'sn': self.service.getServiceName(),
                 'id': oldid.name,
                 'client': oldclient,
                 'broker': brokerstr})

            # Here's the part that checks is the currently connected client
            # has a stale connection.  It *shouldn't* happen, but if it did,
            # it would suck to not be able to sign back on because the system
            # wouldn't believe you were logged off.
            if (not oldbroker) or (oldbroker.connected and oldbroker.transport):
                if oldbroker:
                    brokerstr = "%s%s" % (oldbroker.transport.getPeer(),
                                          brokerstr)
                log.msg("%s@%s refusing new client %s from broker %s." %
                        (self.getPerspectiveName(),
                         self.service.getServiceName(),
                         ref, broker))
                raise PerspectiveInUse("This perspective %r already has a "
                                       "client.  (Connected by %r from %s.)"
                                       % (self, oldid.name, brokerstr))
            elif oldbroker:
                log.msg("BUG: Broker %s disconnected but client %s never"
                        "detached.\n(I'm dropping the old client and "
                        "allowing a new one to attach.)" %
                        (oldbroker, self.client,))
                self.brokerDetached(self, self.client, identity, oldbroker)
                # proceed with normal attach
        #endif self.client
        self.client = (ref, identity, broker)
        return self

    def detached(self, ref, identity):
        del self.client

    def sendMessage(self, message):
        """Send a message to my client.

        (This isn't a defined Perspective method, just an example of something
        you would define in your sub-class to use to talk to your client.)
        """
        # Using 'assert' in this case is probably not a good idea for real
        # code.  Define an exception, or choose to let it pass without comment,
        # as your needs see fit.
        assert self.client is not None, "No client to send a message to!"
        # This invokes remote_message(message) on the client object.
        self.client.callRemote("message", message)

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        try:
            del state['client']
        except KeyError:
            pass
        return state
