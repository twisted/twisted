from twisted.spread import pb

class MultipleClientPerspective(pb.Perspective):
    """Many clients may use this Perspective at once."""

    # This example is from twisted.manhole.service.Perspective.

    def __init__(self, perspectiveName, identityName="Nobody"):
        pb.Perspective.__init__(self, perspectiveName, identityName)
        self.clients = {}

    def attached(self, client, identity):
        # The clients dictionary is really only used as a set and not as a
        # mapping, but we go ahead and throw the Identity into the value slot
        # because hey, it's there.
        self.clients[client] = identity
        return self

    def detached(self, client, identity):
        try:
            del self.clients[client]
        except KeyError:
            # This is probably something as benign as the client being removed
            # by a DeadReferenceError in sendMessage and again when the broker
            # formally closes down.  No big deal.
            pass

    def sendMessage(self, message):
        """Pass a message to my clients' console.
        """
        for client in self.clients.keys():
            try:
                client.callRemote('message', message)
            except pb.DeadReferenceError:
                # Stale broker.  This is the error you get if in the process
                # of doing the callRemote, the broker finds out the transport
                # just died, or something along those lines.  So remove that
                # client from our list.
                self.detached(client, None)

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        state['clients'] = {}
        return state
