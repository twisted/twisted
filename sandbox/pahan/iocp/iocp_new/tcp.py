from socket import AF_INET, SOCK_STREAM

import server

class Port(server.SocketPort):
    af = AF_INET
    type = SOCK_STREAM
    proto = 0

