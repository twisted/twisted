# testing xmlrpc finger

try:
    # Python 3
    from xmlrpc.client import Server
except ImportError:
    # Python 2
    from xmlrpclib import Server

server = Server('http://127.0.0.1:8000/RPC2')
print(server.getUser('moshez'))
