from twisted.spread import pb

class SingleClientWithAKickPerspective(pb.Perspective):
    """One client may attach to me at a time.

    If a new client requests to be attached to me, any currently
    connected perspective will be disconnected.
    """

    # This example is from twisted.words.service.Participant.

    client = None

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        try:
            del state['client']
        except KeyError:
            pass
        return state

    def attached(self, client, identity):
        if self.client is not None:
            self.detached(client, identity)
        self.client = client
        return self

    def detached(self, client, identity):
        self.client = None

        # For the case where 'detached' was called by 'attached' wanting to
        # kick someone off, is this all we need to do?  I'm afraid not --
        # no-one ever told the client that it had been detached!  So the
        # client, which will still have a reference to this perspective until
        # its broker dies, will continue to execute methods on it, will
        # continue to get results returned by those methods.  It just won't get
        # events sent to self.client.  Meanwhile, the newly attached client
        # will probably be confused, because its Perspective is doing things
        # the new client did not ask it to do and it thinks it is the only
        # thing connected.
