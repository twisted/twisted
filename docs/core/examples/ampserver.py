from twisted.protocols import amp


class Sum(amp.Command):
    arguments = [(b"a", amp.Integer()), (b"b", amp.Integer())]
    response = [(b"total", amp.Integer())]


class Divide(amp.Command):
    arguments = [(b"numerator", amp.Integer()), (b"denominator", amp.Integer())]
    response = [(b"result", amp.Float())]
    errors = {ZeroDivisionError: b"ZERO_DIVISION"}


class Math(amp.AMP):
    def sum(self, a, b):
        total = a + b
        print(f"Did a sum: {a} + {b} = {total}")
        return {"total": total}

    Sum.responder(sum)

    def divide(self, numerator, denominator):
        result = float(numerator) / denominator
        print(f"Divided: {numerator} / {denominator} = {result}")
        return {"result": result}

    Divide.responder(divide)


def main():
    from twisted.internet import reactor
    from twisted.internet.protocol import Factory

    pf = Factory()
    pf.protocol = Math
    reactor.listenTCP(1234, pf)
    print("started")
    reactor.run()


if __name__ == "__main__":
    main()
