from twisted.application import service

class TimerService(service.Service):

    def __init__(self, step, callable, *args, **kwargs):
        self.step = step
        self.callable = callable
        self.args = args
        self.kwargs = kwargs

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        if d.has_key('_call'):
            del d['_call']
        return d

    def startService(self):
        service.Service.startService(self)
        self._call = reactor.callLater(self.step, self._setupCall)

    def _setupCall(self):
        self.callable(*self.args, **self.kwargs)
        self._call = reactor.callLater(self.step, self._setupCall)

    def stopService(self):
        service.Service.stopService(self)
        self._call.cancel()
