class ResultQueue:
    """
    I am useful for implementing a pipelining protocol.
    """
    def push(self, d, sink, errsink):
        self.deferreds.append(d)
        d.addCallback(self._cbGotIt, sink, d)
        d.addErrback(self._cbGotIt, errsink, d)

    def pushPlain(self, thing, sink):
        self.deferreds.append((sink, thing))
        self.runQueue()

    def _cbGotIt(self, r, sink, d):
        self.deferreds[self.deferreds.index(d)] = (sink, r)

    def runQueue(self):
        while not isinstance(self.deferreds[0], defer.Deferred):
            sink, r = self.deferreds.pop(0)
            sink(r)

            if not self.deferreds:
                return
