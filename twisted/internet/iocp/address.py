from socket import AF_INET, SOCK_DGRAM, SOCK_STREAM

def getFull(addr, (family, type, protocol)):
    """return a tuple suitable for getHost, getPeer and such"""
    if family == AF_INET:
        return ({SOCK_STREAM: "INET", SOCK_DGRAM: "INET_UDP"}[type],) + addr
    else:
        raise ValueError, "unknown family"

def getPort(addr, (family, type, protocol)):
    """return value suitable for "port starting on\""""
    if family == AF_INET:
        return addr[1]
    else:
        raise ValueError, "unknown family"

def getHost(addr, (family, type, protocol)):
    """return something to pose as hostname"""
    if family == AF_INET:
        return addr[0]
    else:
        raise ValueError, "unknown family"

def getShortProtoName((family, type, protocol)):
    if (family, type) == (AF_INET, SOCK_DGRAM):
        return "UDP"
    else:
        raise ValueError, "unknown family"

