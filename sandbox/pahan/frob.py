from implicitstate import ImplicitStateProtocol as isp

def f(msg):
    print "f got:", msg
p = isp()
p.implicit_state = (f, 4)
