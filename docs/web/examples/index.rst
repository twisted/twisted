
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Examples
========

twisted.web.client
------------------

- :download:`getpage.py` - use ``twisted.web.client.getPage`` to download a web page.
- :download:`dlpage.py` - add callbacks to ``twisted.web.client.downloadPage`` to display errors that occur when downloading a web page


XML-RPC
-------

- :download:`xmlrpc.py` XML-RPC server with several methods, including echoing, faulting, returning deferreds and failed deferreds
- :download:`xmlrpcclient.py` - use ``twisted.web.xmlrpc.Proxy`` to call remote XML-RPC methods
- :download:`advogato.py` - use ``twisted.web.xmlrpc`` to post a diary entry to advogato.org; requires an advogato account


Virtual hosts and proxies
-------------------------

- :download:`proxy.py` - use ``twisted.web.proxy.Proxy`` to make the simplest proxy
- :download:`logging-proxy.py` - example of subclassing the core classes of ``twisted.web.proxy`` to log requests through a proxy
- :download:`reverse-proxy.py` - use ``twisted.web.proxy.ReverseProxyResource`` to make any HTTP request to the proxy port get applied to a specified website
- :download:`rootscript.py` - example use of ``twisted.web.vhost.NameVirtualHost``
- :download:`web.py` - an example of both using the ``processors`` attribute to set how certain file types are treated and using ``twisted.web.vhost.VHostMonsterResource`` to reverse proxy


.rpys and ResourceTemplate
--------------------------

- :download:`hello.rpy.py` - use ``twisted.web.static`` to create a static resource to serve
- :download:`fortune.rpy.py` - create a resource that returns the output of a process run on the server
- :download:`report.rpy.py` - display various properties of a resource, including path, host, and port
- :download:`users.rpy.py` - use ``twisted.web.distrib`` to publish user directories as for a "community web site"
- :download:`simple.rtl` - example use of ``twisted.web.resource.ResourceTemplate``


Miscellaneous
-------------

- :download:`webguard.py` - pairing ``twisted.web`` with ``twisted.cred`` to guard resources against unauthenticated users
- :download:`silly-web.py` - bare-bones distributed web setup with a master and slave using ``twisted.web.distrib`` and ``twisted.spread.pb``
- :download:`soap.py` - use ``twisted.web.soap`` to publish SOAP methods
