# testing xmlrpc finger

try:
    # Python 3
    import xmlrpc.client
    Server = xmlrpc.client.Server
except ImportError:
    # Python 2
    import xmlrpclib
    Server = xmlrpclib.Server

import xmlrpc.client
server = Server('http://127.0.0.1:8000/RPC2')
print(server.getUser('moshez'))
