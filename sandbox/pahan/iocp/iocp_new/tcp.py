from socket import AF_INET, SOCK_STREAM

import abstract

class Port(abstract.SocketPort):
    afPrefix = "INET"
    addressFamily = AF_INET
    socketType = SOCK_STREAM

