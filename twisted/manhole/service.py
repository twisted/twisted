from twisted.spread import pb

import cStringIO
StringIO = cStringIO
del cStringIO

import traceback

class Perspective(pb.Perspective):
    def perspective_do(self, mesg):
        fn = "$manhole"
        try:
            code = compile(mesg, fn, 'eval')
        except:
            try:
                code = compile(mesg, fn, 'exec')
            except:
                io = StringIO.StringIO()
                traceback.print_exc(file=io)
                return io.getvalue()
        try:
            val = eval(code)
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            return io.getvalue()
        return val

class Service(pb.Service):
    # By default, "guest"/"guest" will work as login and password, though you
    # must implement something to retrieve a perspective.
    def getPerspectiveNamed(self, name):
        return Perspective()

if __name__ == '__main__':
    import service
    from twisted.internet.main import Application
    bf = pb.BrokerFactory()
    bf.addService("manhole", service.Service())
    app = Application("manhole")
    app.listenOn(pb.portno, bf)
    app.save()
