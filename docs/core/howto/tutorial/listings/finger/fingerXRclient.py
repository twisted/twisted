# testing xmlrpc finger

from __future__ import print_function

import xmlrpclib
server = xmlrpclib.Server('http://127.0.0.1:8000/RPC2')
print(server.getUser('moshez'))
