from twisted.protocols import amp

class Sum(amp.Command):
    arguments = [('a', amp.Integer()),
                 ('b', amp.Integer())]
    response = [('total', amp.Integer())]

class JustSum(amp.AMP):
    def sum(self, a, b):
        total = a + b
        print 'Did a sum: %d + %d = %d' % (a, b, total)
        return {'total': total}
    Sum.responder(sum)

def main():
    from twisted.internet import reactor
    from twisted.internet.protocol import Factory
    pf = Factory(); pf.protocol = JustSum
    reactor.listenTCP(1234, pf)
    print 'started'
    reactor.run()

if __name__ == '__main__':
    main()
