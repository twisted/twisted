from twisted.cred import perspective

class AnonymousPerspective(perspective.Perspective):
    """Define this as a perspective with whatever capabilities you feel safe
    to give to anonymous users.
    """

class UnattachablePerspective(perspective.Perspective):
    """I am a special class of Perspective that can never be attached to.

    I can be stored in a Service's collection of perspectives and
    placed on an Identity's keyring, but the client will never obtain
    a reference to me.  Instead, they'll get back a single-use
    perspective, of the class named by L{disposablePerspectiveClass}.
    """

    # The code in this example is ALL NEW (and thus not been field-tested or
    # mother-approved), but might be used in CVSToys or BuildBot, where we're
    # publishing public read-only messages and aren't interested in maintaining
    # accounts for the people who sign on to read them.

    disposablePerspectiveClass = AnonymousPerspective
    _counter = 0

    def attached(self, client, identity):
        name = "%s#%d" % (self.name, self._counter)
        self._counter = self._counter + 1
        p = self.disposablePerspectiveClass(name)
        p.setService(self.service)
        # You might add p to the Service's cache of perspectives at this point,
        # so s.getPerspectiveNamed(p.getPerspectiveName()) would work.  Just as
        # long as you remember to remove it from the cache when it's through,
        # so you don't leak memory.
        return p.attached(client, identity)

    def detached(self, client, identity):
        assert 0, "How can this be?  Nothing should have ever attached to me."
