from socket import AF_INET, SOCK_DGRAM, SOCK_STREAM

def getFull(addr, family, type, protocol = 0):
    """return a tuple suitable for getHost, getPeer and such"""
    if family == AF_INET:
        return ({SOCK_STREAM: "INET", SOCK_DGRAM: "INET_UDP"}[type],) + addr

def getPort(addr, family, type, protocol = 0):
    """return value suitable for "port starting on\""""
    if family == AF_INET:
        return addr[1]

def getHost(addr, family, type, protocol = 0):
    """return something to pose as hostname"""
    if family == AF_INET:
        return addr[0]
