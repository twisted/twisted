from twisted.cred import error, perspective

class PerspectiveInUse(error.Unauthorized):
    """Raised when a client requests a perspective already connected to another.
    """
    # XXX: Is there any information this exception should carry, i.e.
    #   the Perspective in question.
    #   the client it's currently attached to.
    #   the Identity which attached it.


class SingleClientPerspective(perspective.Perspective):
    """One client may attach to me at a time.

    If another client tries to attach while a previous one is still connected,
    it will encounter a PerspectiveInUse exception.

    @ivar client: The client attached to me, if any.  (Passed by the
        client as the I{client} argument to L{pb.connect}.
    @type client: L{RemoteReference}
    """

    client = None

    def attached(self, ref, identity):
        if self.client is not None:
            raise PerspectiveInUse
        self.client = ref

        # Perspective.attached methods must return a Perspective to tell the
        # caller what they actually ended up being attached to.
        return self

    def detached(self, ref, identity):
        assert ref is self.client, "Detaching something that isn't attached."
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
        # Nor is the 'message' method defined by twisted.cred -- your client
        # can have any interface you desire, any type of object may be passed
        # to 'attached'.
        self.client.message(message)

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        # References to clients generally aren't persistable.
        try:
            del state['client']
        except KeyError:
            pass
        return state
