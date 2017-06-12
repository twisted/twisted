Ticket numbers in this file can be looked up by visiting
http://twistedmatrix.com/trac/ticket/<number>

.. towncrier release notes start

Twisted 17.5.0 (2017-06-04)
===========================

Bugfixes
--------

- spawnProcess no longer opens an unwanted console on Windows (#5726)
- The transition to the hyperlink package adds IPv6 support to
  twisted.python.url.URL. This is now deprecated and new code should use
  hyperlink directly (see #9126). (#8069)
- twisted.logger now buffers only 200 events by default (reduced from 65536)
  while waiting for observers to be configured. (#8164)
- The transition of twisted.python.url to using the hyperlink package enables a
  URL.click() with no arguments (or 0-length string argument) to resolve dot
  segments in the path. (#8184)
- twisted.protocols.finger now works on Python 3. (#8230)
- TLS-related tests now pass when run with OpenSSL 1.1.0. This makes tests pass
  again on macOS and Windows, as cryptography 1.8 and later include OpenSSL
  1.1.0. (#8898)
- UNIX socket endpoints now process all messages from recvmsg's ancillary data
  via twisted.internet.unix.Server.doRead/twisted.internet.unix.Client.doRead,
  while discarding and logging ones that don't contain file descriptors.
  (#8912)
- twisted.internet.endpoints.HostnameEndpoint and twisted.web.client.Agent work
  again with reactors that do not provide IReactorPluggableNameResolver. This
  undoes the changes that broke downstream users such as treq.testing. Note
  that passing reactors that do not provide IReactorPluggableNameResolver to
  either is deprecated. (#9032)
- A Python 3 Perspective Broker server which receives a remote call with
  keyword arguments from a Python 2 client will now decode any keys which are
  binary to strings instead of crashing. This fixes interoperability between
  Python 2 Buildbot clients and Python 3 Buildbot servers. (#9047)
- twisted.internet._threadedselect now works on both Python 2 and 3. (#9053)
- twisted.internet.interfaces.IResolverSimple implementers will now always be
  passed bytes, properly IDNA encoded if required, on Python 2. On Python 3,
  they will now be passed correctly IDNA-encoded Unicode forms of the domain,
  taking advantage of the idna library from PyPI if possible. This is to avoid
  Python's standard library (which has an out of date idna module) from mis-
  encoding domain names when non-ASCII Unicode is passed to it. (#9137)


Improved Documentation
----------------------

- The examples in Twisted howto "Using the Twisted Application Framework",
  section "Customizing twistd logging" have been updated to use latest logging
  modules and syntax (#9084)


Features
--------

- twisted.internet.defer.Deferred.asFuture and
  twisted.internet.defer.Deferred.fromFuture were added, allowing for easy
  transitions between asyncio coroutines (which await Futures) and twisted
  coroutines (which await Deferreds). (#8748)
- twisted.application.internet.ClientService.whenConnected now accepts an
  argument "failAfterFailures". If you set this to 1, the Deferred returned by
  whenConnected will errback when the connection attempt fails, rather than
  retrying forever. This lets you react (probably by stopping the
  ClientService) to connection errors that are likely to be persistent, such as
  using the wrong hostname, or not being connected to the internet at all.
  (#9116)
- twisted.protocols.tls.TLSMemoryBIOProtocol and anything that uses it
  indirectly including the TLS client and server endpoints now enables TLS 1.3
  cipher suites. (#9128)


Misc
----

- #8133, #8995, #8997, #9003, #9015, #9021, #9026, #9027, #9049, #9057, #9062,
  #9065, #9069, #9070, #9072, #9074, #9075, #9111, #9117, #9140, #9144, #9145


Deprecations and Removals
-------------------------

- twisted.runner.inetdconf.InvalidRPCServicesConfError,
  twisted.runner.inetdconf.RPCServicesConf, twisted.runner.inetdtap.RPCServer,
  and twisted.runner.portmap, deprecated since 16.2.0, have been removed.
  (#8464)
- twisted.python.url and twisted.python._url were modified to rely on
  hyperlink, a new package based on the Twisted URL implementation. Hyperlink
  adds support for IPv6 (fixing #8069), correct username/password encoding,
  better scheme/netloc inference, improved URL.click() behavior (fixing #8184),
  and more. For full docs see hyperlink.readthedocs.io and the CHANGELOG in the
  hyperlink GitHub repo. (#9126)


Conch
-----

Bugfixes
~~~~~~~~

- History-aware terminal protocols like twisted.conch.manhole.Manhole no longer
  raise a TypeError when a user visits a partial line they added to the command
  line history by pressing up arrow before return. (#9031)
- The telnet_echo.tac example had conflicting port callouts between runtime and
  documentation. File was altered to run on documented port, 6023. (#9055)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Remove diffie-hellman-group1-sha1 from twisted.conch. See https://weakdh.org/
  (#9019)
- Removed small and obscure elliptic curves from conch. The only curves conch
  supports now are the ones also supported by OpenSSH. (#9088)


Mail
----

Bugfixes
~~~~~~~~

- twisted.mail.smtp has been ported to Python 3. (#8770)


Names
-----

Bugfixes
~~~~~~~~

- RRHeader now converts its ttl argument to an integer, raising a TypeError if
  it cannot. (#8340)


Web
---

Bugfixes
~~~~~~~~

- twisted.web.cgi now works on Python 3 (#8009)
- twisted.web.distrib now works on Python 3 (#8010)
- twisted.web.http.HTTPFactory now propagates its reactor's callLater method to
  the HTTPChannel object, rather than having callLater grab the global reactor.
  This prevents the possibility of HTTPFactory logging using one reactor, but
  HTTPChannel running timeouts on another. (#8904)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- twisted.web.template.flattenString docstring now correctly references
  io.BytesIO (rather than NativeStringIO). (#9028)


Features
~~~~~~~~

- twisted.web.client now exposes the RequestGenerationFailed exception type.
  (#5310)
- twisted.web.client.Agent will now parse responses that begin with a status
  line that is missing a phrase. (#7673)
- twisted.web.http.HTTPChannel and twisted.web._http2.H2Connection have been
  enhanced so that after they time out they wait a small amount of time to
  allow the connection to close gracefully and, if it does not, they forcibly
  close it to avoid allowing malicious clients to forcibly keep the connection
  open. (#8902)


Misc
~~~~

- #8981, #9018, #9067, #9090, #9092, #9093, #9096


Words
-----

Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.words.protocols.oscar, which is client code for Oscar/ICQ, was
  deprecated in 16.2.0 and has now been removed. (#9024)


Twisted Core 17.1.0 (2017-02-04)
================================

Features
--------
 - Added a new interface,
   twisted.internet.interfaces.IHostnameResolver, which is an
   improvement to twisted.internet.interfaces.IResolverSimple that
   supports resolving multiple addresses as well as resolving IPv6
   addresses.  This is a native, asynchronous, Twisted analogue to
   getaddrinfo. (#4362)
 - twisted.web.client.Agent now uses HostnameEndpoint internally; as a
   consequence, it now supports IPv6, as well as making connections
   faster and more reliably to hosts that have more than one DNS name.
   (#6712)
 - twisted.internet.ssl.CertificateOptions now has the new constructor
   argument 'raiseMinimumTo', allowing you to increase the minimum TLS
   version to this version or Twisted's default, whichever is higher.
   The additional new constructor arguments 'lowerMaximumSecurityTo'
   and 'insecurelyLowerMinimumTo' allow finer grained control over
   negotiated versions that don't honour Twisted's defaults, for
   working around broken peers, at the cost of reducing the security
   of the TLS it will negotiate. (#6800)
 - twisted.internet.ssl.CertificateOptions now sets the OpenSSL
   context's mode to MODE_RELEASE_BUFFERS, which will free the
   read/write buffers on idle TLS connections to save memory. (#8247)
 - trial --help-reactors will only list reactors which can be
   imported.  (#8745)
 - twisted.internet.endpoints.HostnameEndpoint now uses the passed
   reactor's implementation of
   twisted.internet.interfaces.IReactorPluggableResolver to resolve
   hostnames rather than its own deferToThread/getaddrinfo wrapper;
   this makes its hostname resolution pluggable via a public API.
   (#8922)
 - twisted.internet.reactor.spawnProcess now does not emit a
   deprecation warning on Unicode arguments. It will encode Unicode
   arguments down to bytes using the filesystem encoding on UNIX and
   Python 2 on Windows, and pass Unicode through unchanged on Python 3
   on Windows. (#8941)
 - twisted.trial._dist.test.test_distreporter now works on Python 3.
   (#8943)

Bugfixes
--------
 - trial --help-reactors will now display iocp and win32er reactors
   with Python 3. (#8745)
 - twisted.logger._flatten.flattenEvent now handles log_format being
   None instead of assuming the value is always a string. (#8860)
 - twisted.protocol.ftp is now Python 3 compatible (#8865)
 - twisted.names.client.Resolver can now resolve names with IPv6 DNS
   servers. (#8877)
 - twisted.application.internet.ClientService now waits for existing
   connections to disconnect before trying to connect again when
   restarting. (#8899)
 - twisted.internet.unix.Server.doRead and
   twisted.internet.unix.Client.doRead no longer fail if recvmsg's
   ancilliary data contains more than one file descriptor. (#8911)
 - twist on Python 3 now correctly prints the help text when given no
   plugin to run. (#8918)
 - twisted.python.sendmsg.sendmsg no longer segfaults on Linux +
   Python 2. (#8969)
 - IHandshakeListener providers connected via SSL4ClientEndpoint will
   now have their handshakeCompleted methods called. (#8973)
 - The twist script now respects the --reactor option. (#8983)
 - Fix crash when using SynchronousTestCase with Warning object which
   does not store a string as its first argument (like
   libmysqlclient). (#9005)
 - twisted.python.compat.execfile() does not open files with the
   deprecated 'U' flag on Python 3. (#9012)

Deprecations and Removals
-------------------------
 - twisted.internet.ssl.CertificateOption's 'method' constructor
   argument is now deprecated, in favour of the new 'raiseMinimumTo',
   'lowerMaximumSecurityTo', and 'insecurelyLowerMinimumTo' arguments.
   (#6800)
 - twisted.protocols.telnet (not to be confused with the supported
   twisted.conch.telnet), deprecated since Twisted 2.5, has been
   removed. (#8925)
 - twisted.application.strports.parse, as well as the deprecated
   default arguments in strports.service/listen, deprecated since
   Twisted 10.2, has been removed. (#8926)
 - twisted.web.client.getPage and twisted.web.client.downloadPage have
   been deprecated in favour of https://pypi.org/project/treq and
   twisted.web.client.Agent. (#8960)
 - twisted.internet.defer.timeout is deprecated in favor of
   twisted.internet.defer.Deferred.addTimeout (#8971)

Other
-----
 - #7879, #8583, #8764, #8809, #8859, #8906, #8910, #8913, #8916,
   #8934, #8945, #8949, #8950, #8952, #8953, #8959, #8962, #8963,
   #8967, #8975, #8976, #8993, #9013


Twisted Conch 17.1.0 (2017-02-04)
=================================

Features
--------
 - twisted.conch.manhole now works on Python 3. (#8327)
 - Twisted Conch now supports ECDH key exchanges. (#8730)
 - Add support in twisted.conch.ssh for hmac-sha2-384 (#8784)
 - conch and cftp scripts now work on Python 3. (#8791)
 - twisted.conch.ssh supports ECDH key exchange. (#8811)

Bugfixes
--------
 - twisted.conch.ssh.keys.Key.fromString now supports OpenSSL private
   keys with Windows line endings (\r\n) again (broken since 16.6.0).
   (#8928)

Improved Documentation
----------------------
 - The documentation for
   twisted.conch.endpoints.SSHCommandClientEndpoint.existingConnection
   now describes where the value for the connection parameter might
   come from. (#8892)

Other
-----
 - #8890, #8894, #8957, #8958, #8968


Twisted Mail 17.1.0 (2017-02-04)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.tap (the twist plugin for mail) no longer accepts the
   --pop3s option or implicit port numbers to --pop3 and --smtp. This
   functionality has been deprecated since 11.0. (#8920)


Twisted Names 17.1.0 (2017-02-04)
=================================

Bugfixes
--------
 - twisted.names.authority.BindAuthority has been ported to Python 3.
   (#8880)


Twisted News 17.1.0 (2017-02-04)
================================

No significant changes have been made for this release.


Twisted Pair 17.1.0 (2017-02-04)
================================

No significant changes have been made for this release.


Twisted Runner 17.1.0 (2017-02-04)
==================================

Bugfixes
--------
 - On Python 3, procmon now handles process output without exceptions
   (#8919)


Twisted Web 17.1.0 (2017-02-04)
===============================

Features
--------
 - twisted.web.client.Agent now sets ``Content-Length: 0`` for PUT and
   POST requests made without a body producer. (#8984)

Bugfixes
--------
 - twisted.web.http.HTTPFactory now times connections out after one
   minute of no data from the client being received, before the
   request is complete, rather than twelve hours. (#3746)
 - twisted.web.http.HTTPChannel, the server class for Twisted's
   HTTP/1.1 server, now exerts backpressure against clients that do
   not read responses. This means that if a client stops reading from
   a socket for long enough, Twisted will stop reading further
   requests from that client until it consumes some responses. (#8868)
 - twisted.web.http_headers.Headers.getRawHeaders no longer attempts
   to decode the default value when called with a unicode header name.
   (#8974)
 - twisted.web.http.HTTPChannel is less likely to leak file
   descriptors when timing out clients using HTTPS connections. In
   some cases it is still possible to leak a file descriptor when
   timing out HTTP clients: further patches will address this issue.
   (#8992)

Other
-----
 - #7744, #8909, #8935


Twisted Words 17.1.0 (2017-02-04)
=================================

No significant changes have been made for this release.


Twisted Core 16.6.0 (2016-11-17)
================================

Features
--------
 - The twist script can now be run by invoking python -m twisted.
   (#8657)
 - twisted.protocols.sip has been ported to Python 3. (#8669)
 - twisted.persisted.dirdbm has been ported to Python 3. (#8888)

Bugfixes
--------
 - twisted.internet.defer.Deferred now implements send, not __send__,
   which means that it is now a conforming generator. (#8861)
 - The IOCP reactor no longer transmits the contents of uninitialized
   memory when writing large amounts of data. (#8870)
 - Deferreds awaited/yielded from in a
   twisted.internet.defer.ensureDeferred wrapped coroutine will now
   properly raise exceptions. Additionally, it more closely models
   asyncio.ensure_future and will pass through Deferreds. (#8878)
 - Deferreds that are paused or chained on other Deferreds will now
   return a result when yielded/awaited in a twisted.internet.defer
   .ensureDeferred-wrapped coroutine, instead of returning the
   Deferred it was chained to. (#8890)

Improved Documentation
----------------------
 - twisted.test.proto_helpers is now explicitly covered by the
   compatibility policy. (#8857)

Other
-----
 - #8281, #8823, #8862


Twisted Conch 16.6.0 (2016-11-17)
=================================

Features
--------
 - twisted.conch.ssh.keys supports ECDSA keys (#8798)
 - scripts/ckeygen can now generate ecdsa keys. (#8828)
 - ckeygen has been ported to Python 3 (#8855)

Deprecations and Removals
-------------------------
 - twisted.conch.ssh no longer uses gmpy, if available. gmpy is
   unmaintained, does not have binary wheels for any platforms, and an
   alternative for higher performance is available in the form of
   PyPy. (#8079)


Twisted Mail 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Names 16.6.0 (2016-11-17)
=================================

No significant changes have been made for this release.


Twisted News 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Pair 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Runner 16.6.0 (2016-11-17)
==================================

No significant changes have been made for this release.


Twisted Web 16.6.0 (2016-11-17)
===============================

Features
--------
 - twisted.web.server.Site's HTTP/2 server support now emits vastly
   fewer WINDOW_UPDATE frames than previously. (#8681)

Bugfixes
--------
 - twisted.web.Agent now tolerates receiving unexpected status codes
   in the 100 range by discarding them, which is what RFC 7231
   recommends doing. (#8885)
 - twisted.web._http.H2Stream's getHost and getPeer implementations
   now actually return the host and peer instead of None. (#8893)


Twisted Words 16.6.0 (2016-11-17)
=================================

Features
--------
 - twisted.words.protocols.irc has been ported to Python 3 (#6320)


Twisted Core 16.5.0 (2016-10-28)
================================

Features
--------
 - Added twisted.internet.defer.Deferred.addTimeout method to enable
   timeouts of deferreds. (#5786)
 - Perspective Broker (the twisted.spread package) has been ported to
   Python 3 (#7598)
 - 'yield from' can now be used on Deferreds inside generators, when
   the generator is wrapped with
   twisted.internet.defer.ensureDeferred. (#8087)
 - twisted.internet.asyncioreactor has been added, which is a Twisted
   reactor on top of Python 3.4+'s native asyncio reactor. It can be
   selected by passing "--reactor=asyncio" to Twisted tools (twistd,
   Trial, etc) on platforms that support it (Python 3.4+). (#8367)
 - twisted.python.zippath now works on Windows with Python 3. (#8747)
 - twisted.internet.cfreactor is ported to Python 3 and supported on
   2.7 and 3.5+. (#8838)

Bugfixes
--------
 - twisted.internet.test.test_iocp and twisted.internet.test.test_tcp
   have been fixed to work under Python 3 with the Windows IOCP
   reactor (#8631)
 - Arguments to processes on Windows are now passed mbcs-encoded
   arguments.  This prevents process-related tests from hanging on
   Windows with Python 3. (#8735)
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, no longer accept 3DES-
   based cipher suites by default, to defend against SWEET32. (#8781)
 - twisted.logger.jsonFileLogObserver no longer emits non-JSON
   tracebacks into its file; additionally,
   twisted.logger.formatEventAsClassicLogText now includes traceback
   information for the log event it formats. (#8858)
 - twisted.python.version now exports a version of Incremental that is
   16.10.1 or higher, making t.p.v.Version package name comparisons
   case-insensitive. (#8863)
 - twisted.python.reflect.safe_str encodes unicode as ascii with
   backslashreplace error handling on Python 2. (#8864)

Improved Documentation
----------------------
 - The twisted.internet.interfaces.IProtocol.dataReceived() method
   takes one parameter of type bytes.  This has been clarified in the
   doc string. (#8763)

Deprecations and Removals
-------------------------
 - twisted.python.constants is deprecated in preference to constantly
   on PyPI, which is the same code rolled into its own package.
   (#7351)
 - twisted.python.dist3 has been made private API. (#8761)
 - When the source code is checked out, bin/trial is no longer in the
   tree.  Developers working on the Twisted source code itself should
   either (1) run all tests under tox, or (2) run 'python setup.py
   develop' to install trial before running any tests. (#8765)
 - twisted.protocols.gps, deprecated since Twisted 15.2, has been
   removed. (#8787)

Other
-----
 - #4926, #7868, #8209, #8214, #8271, #8308, #8324, #8348, #8367,
   #8377, #8378, #8379, #8380, #8381, #8383, #8385, #8387, #8388,
   #8389, #8391, #8392, #8393, #8394, #8397, #8406, #8410, #8412,
   #8413, #8414, #8421, #8425, #8426, #8430, #8432, #8434, #8435,
   #8437, #8438, #8439, #8444, #8451, #8452, #8453, #8454, #8456,
   #8457, #8459, #8462, #8463, #8465, #8468, #8469, #8479, #8482,
   #8483, #8486, #8490, #8493, #8494, #8496, #8497, #8498, #8499,
   #8501, #8503, #8504, #8507, #8508, #8510, #8513, #8514, #8515,
   #8516, #8517, #8520, #8521, #8522, #8523, #8524, #8527, #8528,
   #8529, #8531, #8532, #8534, #8536, #8537, #8538, #8543, #8544,
   #8548, #8552, #8553, #8554, #8555, #8557, #8560, #8563, #8565,
   #8568, #8569, #8572, #8573, #8574, #8580, #8581, #8582, #8586,
   #8589, #8590, #8592, #8593, #8598, #8603, #8604, #8606, #8609,
   #8615, #8616, #8617, #8618, #8619, #8621, #8622, #8624, #8627,
   #8628, #8630, #8632, #8634, #8640, #8644, #8645, #8646, #8647,
   #8662, #8664, #8666, #8668, #8671, #8672, #8677, #8678, #8684,
   #8691, #8702, #8705, #8706, #8716, #8719, #8724, #8725, #8727,
   #8734, #8741, #8749, #8752, #8754, #8755, #8756, #8757, #8758,
   #8767, #8773, #8776, #8779, #8780, #8785, #8788, #8789, #8790,
   #8792, #8793, #8799, #8808, #8817, #8839, #8845, #8852


Twisted Conch 16.5.0 (2016-10-28)
=================================

Features
--------
 - SSH key fingerprints can be generated using base64 encoded SHA256
   hashes. (#8701)

Bugfixes
--------
 - SSHUserAuthServer does not crash on keyboard interactive
   authentication when running on Python 3 (#8771)
 - twisted.conch.insults.insults.ServerProtocol no longer corrupts a
   client's display when attempting to set the cursor position, and
   its ECMA-48 terminal manipulation works on Python 3. (#8803)

Other
-----
 - #8495, #8511, #8715, #8851


Twisted Mail 16.5.0 (2016-10-28)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.protocols.DomainSMTP and DomainESMTP, deprecated since
   2003, have been removed. (#8772)

Other
-----
 - #6289, #8525, #8786, #8830


Twisted Names 16.5.0 (2016-10-28)
=================================

No significant changes have been made for this release.

Other
-----
 - #8625, #8663


Twisted News 16.5.0 (2016-10-28)
================================

No significant changes have been made for this release.


Twisted Pair 16.5.0 (2016-10-28)
================================

Features
--------
 - twisted.pair has been ported to Python 3 (#8744)


Twisted Runner 16.5.0 (2016-10-28)
==================================

No significant changes have been made for this release.


Twisted Web 16.5.0 (2016-10-28)
===============================

Bugfixes
--------
 - twisted.web.client.HTTPConnectionPool and anything that uses it,
   like twisted.web.client.Agent, have had their logic for resuming
   transports changed so that transports are resumed after state
   machine transitions are complete, rather than before. This change
   allows the HTTP client infrastructure to work with alternative HTTP
   implementations such as HTTP/2 which may be able to deliver a
   complete response synchronously when producing is resumed. (#8720)

Other
-----
 - #8519, #8530, #8629, #8707, #8777, #8778, #8844


Twisted Words 16.5.0 (2016-10-28)
=================================

No significant changes have been made for this release.

Other
-----
 - #8360, #8460


Twisted Core 16.4.1 (2016-09-07)
================================

Features
--------
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, now support ChaCha20
   ciphers when available from the OpenSSL on the system. (#8760)

Bugfixes
--------
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, no longer accept 3DES-
   based cipher suites by default, to defend against SWEET32. (#8781)


Twisted Conch 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted Mail 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Names 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted News 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Pair 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Runner 16.4.1 (2016-09-07)
==================================

No significant changes have been made for this release.


Twisted Web 16.4.1 (2016-09-07)
===============================

No significant changes have been made for this release.


Twisted Words 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted Core 16.4.0 (2016-08-25)
================================

Features
--------
 - Add twisted.application.twist, meant to eventually replace twistd
   with a simpler interface.  Add twisted.application.runner API,
   currently private, which twist is built on. (#5705)
 - The new interface IHandshakeListener that can be implemented by any
   Protocol provides a callback that is called when the TLS handshake
   has been completed, allowing Protocols to make decisions about the
   TLS configuration before application data is sent. (#6024)
 - twisted.python.syslog has been ported to Python 3. (#7957)
 - twisted.internet.defer.ensureDeferred has been added, similar to
   asyncio's ensure_future. Wrapping a coroutine (the result of a
   function defined using async def, available only on Python 3.5+)
   with it allows you to use the "await" keyword with Deferreds inside
   the coroutine, similar to "yield" when using inlineCallbacks.
   (#8088)
 - twisted.internet.inotify have been ported to Python 3 (#8211)
 - twisted.enterprise has been ported to Python 3. The third-party
   pysqlite2 package has not been ported to Python 3, so any database
   connector based on pysqlite2 cannot be used. Instead the sqlite3
   module included with Python 3 should be used. (#8303)
 - Scripts such as cftp, ckeygen, conch, mailmail, pyhtmlizer,
   tkconch, twistd and trial have been updated to be setuptools
   console scripts.  (#8491)
 - twisted.pair.raw and twisted.pair.rawudp have been ported to Python
   3 (#8545)
 - twisted.internet.baseprocess has been ported to Python 3. (#8546)
 - twisted.python.dist has been ported to Python 3 (#8556)
 - twisted.internet.interfaces.IOpenSSLContextFactory has been added,
   which defines the interface provided both by the old-style
   twisted.internet.ssl.ContextFactory class and the newer
   twisted.interface.ssl.CertificateOptions class. This is a precursor
   to formally deprecating the former class in favour of the latter.
   (#8597)
 - twisted.python.zipstream has been ported to Python 3 (#8607)
 - Zip file entries returned by ChunkingZipFile.readfile() are now
   context managers. (#8641)
 - twisted.protocols.socks has been ported to Python 3 (#8665)
 - twisted.spread.banana has been ported to Python 3 (#8667)
 - Trial can now be invoked via "python -m twisted.trial". (#8712)
 - twisted.protocols.postfix has been ported to Python 3 (#8713)
 - twisted.protocols.wire and twisted.protocols.portforwarding have
   been ported to Python 3 (#8717)
 - twisted.protocols.stateful has been ported to Python 3 (#8718)
 - twisted.protocols.memcache is now compatible with Python 3. (#8726)
 - twisted.protocols.dict has been ported to Python 3 (#8732)

Bugfixes
--------
 - pip install -e ".[dev]" now works on Python 3, but it will not
   install twistedchecker or pydoctor, which have not yet been ported.
   (#7807)
 - twistd can now properly daemonize on Linux/Unix when run under
   Python3 and will not hang indefinitely. (#8155)
 - tox can now be used to run Twisted's tests on Windows (#8578)
 - twisted.python.filepath.setContent() and
   twisted.python.filepath.moveTo() now work on Windows with Python 3
   (#8610)
 - twisted.internet.win32eventreactor works on Python 3 in Windows
   (#8626)
 - The TLS payload buffer size was reduced in
   twisted.protocols.tls.TLSMemoryBIOProtocol.  This fixes writing of
   very long strings using the TLSv1_1 method from the OpenSSL
   library. (#8693)
 - twisted.logger._flatten.flattenEvent() now does not crash if passed
   a unicode string. (#8699)
 - twisted.application.strports.service (and thus twistd) no longer
   swallow asynchronous exceptions from IStreamServerEndpoint.listen.
   (#8710)
 - _twistd_unix now reports the name and encoded message of an
   exception raised during daemonization on Python 2 and 3. (#8731)
 - twisted.protocols.amp now handles floats on Python 3. Previously,
   sending a float would raise a ValueError. (#8746)

Improved Documentation
----------------------
 - Some broken links to xprogramming in the unit test documentation
   have been fixed. (#8579)
 - The Twisted Tutorial "The Evolution of Finger" has been updated to
   use endpoints throughout. (#8588)
 - Updated the mail examples to use endpoints and better TLS. (#8595)
 - Changed the Twisted Web howto to use endpoints and modern TLS.
   (#8596)
 - Updated bug report URL in man pages. (#8600)
 - In twisted.internet.udp.Port, write() takes a parameter of type
   bytes.  This is clarified in the docstring. (#8635)
 - twisted.internet.interfaces.ITransport.write() and
   twisted.internet.interfaces.ITransport.writeSequence() take bytes
   parameters. (#8636)
 - twisted.python.filepath.AbstractFilePath.getContent() returns
   bytes.  The docstring was updated to clarify this. (#8637)
 - Updated release notes to reflect that 15.4 is the last version that
   supported Python 2.6, not 15.5. (#8651)
 - A missing space in defer.rst resulted in badly rendered output. The
   space was added. (#8723)

Deprecations and Removals
-------------------------
 - Dropped support for pyOpenSSL versions less than 16.0.0. (#8441)

Other
-----
 - #4926, #7868, #8209, #8271, #8276, #8308, #8324, #8348, #8367,
   #8377, #8378, #8379, #8380, #8381, #8383, #8385, #8386, #8387,
   #8388, #8389, #8391, #8392, #8393, #8394, #8397, #8406, #8410,
   #8412, #8413, #8414, #8421, #8425, #8426, #8428, #8429, #8430,
   #8432, #8434, #8435, #8437, #8438, #8439, #8444, #8451, #8452,
   #8453, #8454, #8456, #8457, #8459, #8462, #8463, #8465, #8468,
   #8469, #8479, #8482, #8483, #8486, #8490, #8493, #8494, #8496,
   #8497, #8498, #8499, #8501, #8503, #8504, #8507, #8508, #8510,
   #8513, #8514, #8515, #8516, #8517, #8520, #8521, #8522, #8523,
   #8524, #8527, #8528, #8529, #8531, #8532, #8534, #8536, #8537,
   #8538, #8540, #8541, #8543, #8548, #8552, #8553, #8554, #8555,
   #8557, #8560, #8563, #8565, #8568, #8569, #8572, #8573, #8574,
   #8577, #8580, #8581, #8582, #8584, #8586, #8589, #8590, #8592,
   #8593, #8598, #8603, #8604, #8606, #8609, #8615, #8616, #8617,
   #8618, #8619, #8621, #8624, #8627, #8628, #8630, #8632, #8634,
   #8640, #8644, #8645, #8646, #8647, #8648, #8662, #8664, #8666,
   #8668, #8671, #8672, #8684, #8691, #8702, #8703, #8705, #8706,
   #8716, #8719, #8724, #8725, #8727, #8733, #8734, #8741


Twisted Conch 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.conch.ssh.address is now ported to Python 3. (#8495)
 - twisted.conch.ssh.transport is now ported to Python 3. (#8638)
 - twisted.conch.ssh.channel is now ported to Python 3. (#8649)
 - twisted.conch.ssh.userauth is now ported to Python 3. (#8654)
 - twisted.conch.ssh.connection is now ported to Python 3. (#8660)
 - twisted.conch.ssh.session is now ported to Python 3. (#8661)
 - twisted.conch.ssh.filetransfer is now ported to Python 3. (#8675)
 - twisted.conch.ssh.agent is now ported to Python 3. (#8686)
 - twisted.conch.ssh is now ported to Python 3. (#8690)
 - twisted.conch.openssh_compat.* is now ported to Python 3. (#8694)
 - twisted.conch.client.knownhosts is now ported to Python 3. (#8697)
 - twisted.conch.insults.insults has been ported to Python 3 (#8698)
 - twisted.conch.client.default is now ported to Python 3. (#8700)
 - twisted.conch.recvline has been ported to Python 3 (#8709)
 - twisted.conch.endpoints is now ported to Python 3. (#8722)

Bugfixes
--------
 - The SSHService is now a bytestring (#8653)
 - The name field in SShChannel is now a bytestring (#8683)

Improved Documentation
----------------------
 - Fixed syntax errors in cftp man page. (#8601)

Other
-----
 - #8495, #8511, #8715


Twisted Mail 16.4.0 (2016-08-25)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.mail.DomainWithDefaultDict.has_key is now deprecated
   in favor of the `in` keyword. (#8361)
 - twisted.mail.protocols.SSLContextFactory, deprecated since Twisted
   12.0, has been removed. (#8591)

Other
-----
 - #8525


Twisted Names 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.names.srvconnect is now ported to Python 3. (#8262)
 - twisted.names.resolve and twisted.names.tap have been ported to
   Python 3 (#8550)

Other
-----
 - #8625, #8663


Twisted News 16.4.0 (2016-08-25)
================================

No significant changes have been made for this release.


Twisted Pair 16.4.0 (2016-08-25)
================================

No significant changes have been made for this release.


Twisted Runner 16.4.0 (2016-08-25)
==================================

Features
--------
 - twisted.runner has been ported to Python 3. (#8739)


Twisted Web 16.4.0 (2016-08-25)
===============================

Features
--------
 - Twisted web HTTP/2 servers now time out HTTP/2 connections in the
   same manner as HTTP/1.1 connections. (#8480)

Bugfixes
--------
 - A bug in twisted.web.server.Site.makeSession which may lead to
   predictable session IDs was fixed.  Session IDs are now generated
   securely using `os.urandom`. (#3460)
 - twisted.web.server.Request.getSession will now, for a request sent
   over HTTPS, set a "Secure" cookie, preventing the secure session
   from being sent over plain-text HTTP. (#3461)
 - If called multiple times, twisted.web.http.Request.setLastModified
   now correctly observes the greatest supplied value. (#3807)
 - The HTTP server now correctly times connections out. (broken in
   16.2) (#8481)
 - Twisted's HTTP/2 support no longer throws priority exceptions when
   WINDOW_UDPATE frames are received after a response has been
   completed. (#8558)
 - twisted.web.twcgi.CGIScript will now not pass the "Proxy" header to
   CGI scripts, as a mitigation to CVE-2016-1000111. (#8623)
 - Twisted Web's HTTP/2 server can now tolerate streams being reset by
   the client midway through a data upload without throwing
   exceptions. (#8682)
 - twisted.web.http.Request now swallows header writes on reset HTTP/2
   streams, rather than erroring out. (#8685)
 - twisted.web's HTTP/2 server now tolerates receiving WINDOW_UPDATE
   frames for streams for which it has no outstanding data to send.
   (#8695)
 - twisted.web.http.HTTPChannel now resumes producing on finished,
   non-persistent connections. This prevents HTTP/1 servers using TLS
   from leaking a CLOSE_WAIT socket per request. (#8766)

Other
-----
 - #8519, #8530, #8629, #8707


Twisted Words 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.words.xish is now ported to Python 3 (#8337)
 - twisted.words.protocols.jabber is now ported to Python 3 (#8423)
 - twisted.words.protocols.irc.ERR_TOOMANYMATCHES was introduced
   according to the RFC 2812 errata. (#8585)

Bugfixes
--------
 - twisted.words.protocols.irc.RPL_ADMINLOC was removed and replaced
   with twisted.words.protocols.irc.RPL_ADMINLOC1 and
   twisted.words.protocols.irc.RPL_ADMINLOC2 to match the admin
   commands defined in RFC 2812. (#8585)
 - twisted.words.protocols.jabber.sasl_mechanisms has been fixed for
   Python 3.3 (#8738)

Improved Documentation
----------------------
 - The XMPP client example now works on Python 3. (#8509)

Other
-----
 - #8360, #8460


Twisted Core 16.3.0 (2016-07-05)
================================

Features
--------
 - Defined a new interface, IProtocolNegotiationFactory, that can be
   implemented by IOpenSSLClientConnectionCreator or
   IOpenSSLServerConnectionCreator factories to allow them to offer
   protocols for negotiation using ALPN or NPN during the TLS
   handshake. (#8188)
 - twisted.trial.unittest.SynchronousTestCase.assertRegex is now
   available to provide Python 2.7 and Python 3 compatibility. (#8372)

Improved Documentation
----------------------
 - Development documentation has been updated to refer to Git instead
   of SVN. (#8335)

Deprecations and Removals
-------------------------
 - twisted.python.reflect's deprecated functions have been removed.
   This includes funcinfo (deprecated since Twisted 2.5), allYourBase
   and accumulateBases (deprecated since Twisted 11.0), getcurrent and
   isinst (deprecated since Twisted 14.0). (#8293)
 - twisted.scripts.tap2deb and twisted.scripts.tap2rpm (along with the
   associated executables), deprecated since Twisted 15.2, have now
   been removed. (#8326)
 - twisted.spread.ui has been removed. (#8329)
 - twisted.manhole -- not to be confused with manhole in Conch -- has
   been removed. This includes the semi-functional Glade reactor, the
   manhole application, and the manhole-old twistd plugin. (#8330)
 - twisted.protocols.sip.DigestAuthorizer, BasicAuthorizer, and
   related functions have been removed. (#8445)

Other
-----
 - #7229, #7826, #8290, #8323, #8331, #8336, #8341, #8344, #8345,
   #8347, #8351, #8363, #8365, #8366, #8374, #8382, #8384, #8390,
   #8395, #8396, #8398, #8399, #8400, #8401, #8403, #8404, #8405,
   #8407, #8408, #8409, #8415, #8416, #8417, #8418, #8419, #8420,
   #8427, #8433, #8436, #8461


Twisted Conch 16.3.0 (2016-07-05)
=================================

No significant changes have been made for this release.


Twisted Mail 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Names 16.3.0 (2016-07-05)
=================================

Bugfixes
--------
 - twisted.names.client.Resolver as well as all resolvers inheriting
   from twisted.names.common.ResolverBase can now understand DNS
   answers that come back in a different case than the query. Example:
   querying for www.google.com and the answer comes back with an A
   record for www.google.COM will now work. (#8343)


Twisted News 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Pair 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Runner 16.3.0 (2016-07-05)
==================================

No significant changes have been made for this release.


Twisted Web 16.3.0 (2016-07-05)
===============================

Features
--------
 - twisted.web.http.HTTPChannel now implements ITransport. Along with
   this change, twisted.web.http.Request now directs all its writes to
   the HTTPChannel, rather than to the backing transport. This change
   is required for future HTTP/2 work. (#8191)
 - twisted.web.http.HTTPChannel now has a HTTP/2 implementation which
   will be used if the transport has negotiated using it through
   ALPN/NPN (see #8188). (#8194)

Bugfixes
--------
 - twisted.web.client.Agent and twisted.web.client.ProxyAgent now add
   brackets to IPv6 literal addresses in the host header they send.
   (#8369)
 - The HTTP server now correctly times connections out. (broken in
   16.2) (#8481)

Deprecations and Removals
-------------------------
 - twisted.web would previously dispatch pipelined requests
   simultaneously and queue the responses. This behaviour did not
   enforce any of the guarantees required by RFC 7230 or make it
   possible for users to enforce those requirements. For this reason,
   the parallel dispatch of requests has been removed. Pipelined
   requests are now processed serially. (#8320)


Twisted Words 16.3.0 (2016-07-05)
=================================

No significant changes have been made for this release.


Twisted Core 16.2.0 (2016-05-18)
================================

Features
--------
 - twisted.protocols.haproxy.proxyEndpoint provides an endpoint that
   wraps any other stream server endpoint with the PROXY protocol that
   retains information about the original client connection handled by
   the proxy; this wrapper is also exposed via the string description
   prefix 'haproxy'; for example 'twistd web --port haproxy:tcp:8765'.
   (#8203)
 - twisted.application.app.AppLogger (used by twistd) now uses the new
   logging system. (#8235)

Bugfixes
--------
 - twisted.application-using applications (trial, twistd, etc) now
   work with the --reactor option on Python 3. (#8299)
 - Failures are now logged by STDLibLogObserver. (#8316)

Improved Documentation
----------------------
 - Deprecation documentation was extended to include a quick check
   list for developers. (#5645)
 - The Twisted Deprecation Policy is now documented in the Twisted
   Development Policy. (#8082)
 - The documentation examples for UDP now work on Python 3. (#8280)

Deprecations and Removals
-------------------------
 - Passing a factory that produces log observers that do not implement
   twisted.logger.ILogObserver or twisted.python.log.ILogObserver to
   twisted.application.app.AppLogger has been deprecated. This is
   primarily used by twistd's --logger option. Please use factories
   that produce log observers implementing twisted.logger.ILogObserver
   or the legacy twisted.python.log.ILogObserver. (#8235)
 - twisted.internet.qtreactor, a stub that imported the external
   qtreactor, has been removed. (#8288)

Other
-----
 - #6266, #8231, #8244, #8256, #8266, #8269, #8275, #8277, #8286,
   #8291, #8292, #8304, #8315


Twisted Conch 16.2.0 (2016-05-18)
=================================

No significant changes have been made for this release.

Other
-----
 - #8279


Twisted Mail 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Names 16.2.0 (2016-05-18)
=================================

Features
--------
 - twisted.names.server is now ported to Python 3 (#8195)
 - twisted.names.authority and twisted.names.secondary have been
   ported to Python 3 (#8259)


Twisted News 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Pair 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Runner 16.2.0 (2016-05-18)
==================================

Deprecations and Removals
-------------------------
 - twisted.runner.inetdtap and twisted.runner.inetdconf RPC support
   was deprecated as it was broken for a long time. (#8123)


Twisted Web 16.2.0 (2016-05-18)
===============================

Features
--------
 - twisted.web.http.HTTPFactory's constructor now accepts a reactor
   argument, for explicit reactor selection. (#8246)

Bugfixes
--------
 - twisted.web.http.HTTPChannel.headerReceived now respond with 400
   and disconnect when a malformed header is received. (#8101)
 - twisted.web.http.Request once again has a reference to the
   HTTPFactory which created it, the absence of which was preventing
   log messages from being created.  (#8272)
 - twisted.web.http.HTTPChannel no longer processes requests that have
   invalid headers as the final header in their header block. (#8317)
 - twisted.web.client.HTTPClientFactory (and the getPage and
   downloadPage APIs) now timeouts correctly on TLS connections where
   the remote party is not responding on the connection. (#8318)

Other
-----
 - #8300


Twisted Words 16.2.0 (2016-05-18)
=================================

Deprecations and Removals
-------------------------
 - twisted.words.protocols.msn, deprecated since Twisted 15.1, has
   been removed. (#8253)
 - twisted.words.protocols.oscar is deprecated. (#8260)


Twisted Core 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Conch 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted Mail 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Names 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted News 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Pair 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Runner 16.1.1 (2016-04-08)
==================================

No significant changes have been made for this release.


Twisted Web 16.1.1 (2016-04-08)
===============================

Bugfixes
--------
 - twisted.web.http.Request once again has a reference to the
   HTTPFactory which created it, the absence of which was preventing
   log messages from being created.  (#8272)


Twisted Words 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted Core 16.1.0 (2016-04-04)
================================

Features
--------
 - twisted.application.internet.ClientService, a service that
   maintains a persistent outgoing endpoint-based connection; a
   replacement for ReconnectingClientFactory that uses modern APIs.
   (#4735)
 - Twisted now uses setuptools' sdist to build tarballs. (#7985)

Bugfixes
--------
 - Twisted is now compatible with OpenSSL 1.0.2f. (#8189)

Other
-----
 - #4543, #8124, #8193, #8210, #8220, #8223, #8226, #8242


Twisted Conch 16.1.0 (2016-04-04)
=================================

Features
--------
 - twisted.conch.checkers is now ported to Python 3. (#8225)
 - twisted.conch.telnet is now ported to Python 3. (#8228)
 - twisted.conch.manhole_ssh.ConchFactory (used by `twistd manhole`)
   no longer uses a hardcoded SSH server key, and will generate a
   persistent one, saving it in your user appdir. If you use
   ConchFactory, you will now need to provide your own SSH server key.
   (#8229)

Other
-----
 - #8237, #8240


Twisted Mail 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Names 16.1.0 (2016-04-04)
=================================

No significant changes have been made for this release.


Twisted News 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Pair 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Runner 16.1.0 (2016-04-04)
==================================

No significant changes have been made for this release.


Twisted Web 16.1.0 (2016-04-04)
===============================

Features
--------
 - twisted.web.http.Request.addCookie now supports both unicode and
   bytes arguments, with unicode arguments being encoded to UTF-8.
   (#8067)

Bugfixes
--------
 - twisted.web.util.DeferredResource no longer causes spurious
   "Unhandled error in Deferred" log messages. (#8192)
 - twisted.web.server.site.makeSession now generates an uid of type
   bytes on both Python 2 and 3. (#8215)

Other
-----
 - #8238


Twisted Words 16.1.0 (2016-04-04)
=================================

No significant changes have been made for this release.


Twisted Core 16.0.0 (2016-03-10)
================================

Features
--------
 - todo parameter for IReporter.addExpectedSuccess and
   IReporter.addUnexpectedSuccess is no longer required. If not
   provided, a sensible default will be used instead. (#4811)
 - A new string endpoint type, "tls:", allows for properly-verified
   TLS (unlike "ssl:", always matching hostname resolution with
   certificate hostname verification) with faster IPv4/IPv6
   connections.  This comes with an accompanying function,
   twisted.internet.endpoints.wrapClientTLS, which can wrap an
   arbitrary client endpoint with client TLS. (#5642)
 - twisted.python.filepath.makedirs accepts an ignoreExistingDirectory
   flag which ignore the OSError raised by os.makedirs if requested
   directory already exists. (#5704)
 - twisted.protocols.amp has been ported to Python 3. (#6833)
 - twisted.internet.ssl.trustRootFromCertificates returns an object
   suitable for use as trustRoot= to
   twisted.internet.ssl.optionsForClientTLS that trusts multiple
   certificates. (#7671)
 - twisted.python.roots is now ported to Python 3. (#8131)
 - twisted.cred.strports has been ported to Python 3. (#8216)

Bugfixes
--------
 - Expected failures from standard library unittest no longer fail
   with Trial reporters. (#4811)
 - twisted.internet.endpoints.HostnameEndpoint.connect no longer fails
   with an AlreadyCalledError when the Deferred it returns is
   cancelled after all outgoing connection attempts have been made but
   none have yet succeeded or failed. (#8014)
 - twisted.internet.task.LoopingCall.withCount when run with internal
   of 0, now calls the countCallable with 1, regardless of the time
   passed between calls. (#8125)
 - twisted.internet.endpoints.serverFromString, when parsing a SSL
   strports definition, now gives the correct error message when an
   empty chain file is given. (#8222)

Improved Documentation
----------------------
 - The Twisted Project has adopted the Contributor Covenant as its
   Code of Conduct. (#8173)

Deprecations and Removals
-------------------------
 - twisted.internet.task.LoopingCall.deferred is now deprecated. Use
   the deferred returned by twisted.internet.task.LoopingCall.start()
   (#8116)
 - twisted.internet.gtkreactor, the GTK+ 1 reactor deprecated since
   Twisted 10.1, has been removed. This does not affect the GTK2,
   GLib, GTK3, or GObject-Introspection reactors. (#8145)
 - twisted.protocols.mice, containing a Logitech MouseMan serial
   driver, has been deprecated. (#8148)
 - The __version__ attribute of former subprojects (conch, mail,
   names, news, pair, runner, web, and words) is deprecated in
   preference to the central twisted.__version__. (#8219)

Other
-----
 - #6842, #6978, #7668, #7791, #7881, #7943, #7944, #8050, #8104,
   #8115, #8119, #8122, #8139, #8144, #8154, #8162, #8180, #8187,
   #8220


Twisted Conch 16.0.0 (2016-03-10)
=================================

Features
--------
 - twisted.conch now uses cryptography instead of PyCrypto for its
   underlying crypto operations. (#7413)
 - twisted.conch.ssh.keys is now ported to Python 3. (#7998)

Bugfixes
--------
 - twisted.conch.ssh.channel.SSHChannel's getPeer and getHost methods
   now return an object which provides IAddress instead of an old-
   style tuple address. (#5999)
 - twisted.conch.endpoint.SSHCommandClientEndpoint, when
   authentication is delegated to an SSH agent, no longer leaves the
   agent connection opened when connection to the server is lost.
   (#8138)

Other
-----
 - #7037, #7715, #8200, #8208


Twisted Mail 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Names 16.0.0 (2016-03-10)
=================================

No significant changes have been made for this release.


Twisted News 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Pair 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Runner 16.0.0 (2016-03-10)
==================================

No significant changes have been made for this release.


Twisted Web 16.0.0 (2016-03-10)
===============================

Features
--------
 - twisted.web.http_headers._DictHeaders now correctly handles
   updating via keyword arguments in Python 3 (therefore
   twisted.web.http_headers is now fully ported to Python 3). (#6082)
 - twisted.web.wsgi has been ported to Python 3. (#7993)
 - twisted.web.http_headers.Headers now accepts both Unicode and
   bytestring keys and values, encoding to iso-8859-1 and utf8
   respectively. (#8129)
 - twisted.web.vhost ported to Python 3. (#8132)

Bugfixes
--------
 - twisted.web.http.HTTPChannel now correctly handles non-ascii method
   name by returning 400. Previously non-ascii method name was causing
   unhandled exceptions. (#8102)
 - twisted.web.static.File on Python 3 now redirects paths to
   directories without a trailing slash, to a path with a trailing
   slash, as on Python 2. (#8169)

Deprecations and Removals
-------------------------
 - twisted.web.http.Request's headers and received_headers attributes,
   deprecated since Twisted 13.2, have been removed. (#8136)
 - twisted.web.static.addSlash is deprecated. (#8169)

Other
-----
 - #8140, #8182


Twisted Words 16.0.0 (2016-03-10)
=================================

No significant changes have been made for this release.


Twisted Core 15.5.0 (2015-11-28)
================================

Python 3.5 (on POSIX) support has been added.

This release introduces changes that are required for Conch's SSH
implementation to work with OpenSSH 6.9+ servers.

Features
--------
 - twisted.python.url is a new abstraction for URLs, supporting RFC
   3987 IRIs. (#5388)
 - twisted.python.logfile is now ported to Python 3. (#6749)
 - twisted.python.zippath has been ported to Python 3. (#6917)
 - twisted.internet.ssl.CertificateOptions and
   twisted.internet.ssl.optionsForClientTLS now take a
   acceptableProtocols parameter that enables negotiation of the next
   protocol to speak after the TLS handshake has completed. This field
   advertises protocols over both NPN and ALPN. Also added new
   INegotiated interface for TLS interfaces that support protocol
   negotiation. This interface adds a negotiatedProtocol property that
   reports what protocol, if any, was negotiated in the TLS handshake.
   (#7860)
 - twisted.python.urlpath.URLPath now operates correctly on Python 3,
   using bytes instead of strings, and introduces the fromBytes
   constructor to assist with creating them cross-version. (#7994)
 - twisted.application.strports is now ported to Python 3. (#8011)
 - twistd (the Twisted Daemon) is now ported to Python 3. (#8012)
 - Python 3.5 is now supported on POSIX platforms. (#8042)
 - twisted.internet.serialport is now ported on Python 3. (#8099)

Bugfixes
--------
 - twisted.logger.formatEvent now can format an event if it was
   flattened (twisted.logger.eventAsJSON does this) and has text after
   the last replacement field. (#8003)
 - twisted.cred.checkers.FilePasswordDB now logs an error if the
   credentials db file does not exist, no longer raises an unhandled
   error. (#8028)
 - twisted.python.threadpool.ThreadPool now properly starts enough
   threads to do any work scheduled before ThreadPool.start() is
   called, such as when work is scheduled in the reactor via
   reactor.callInThread() before reactor.run(). (#8090)

Improved Documentation
----------------------
 - Twisted Development test standard documentation now contain
   information about avoiding test data files. (#6535)
 - The documentation for twisted.internet.defer.DeferredSemaphore now
   describes the actual usage for limit and tokens instance
   attributes. (#8024)

Deprecations and Removals
-------------------------
 - twisted.python._initgroups, a C extension, has been removed and
   stdlib support is now always used instead. (#5861)
 - Python 2.6 is no longer supported. (#8017)
 - twisted.python.util.OrderedDict is now deprecated, and uses of it
   in Twisted are replaced with collections.OrderedDict. (#8051)
 - twisted.persisted.sob.load, twisted.persisted.sob.loadValueFromFile
   and twisted.persisted.sob.Persistent.save() are now deprecated when
   used with a passphrase. The encyption used by these methods are
   weak. (#8081)
 - twisted.internet.interfaces.IStreamClientEndpointStringParser has
   been removed and Twisted will no longer use parsers implementing
   this interface. (#8094)

Other
-----
 - #5976, #6628, #6894, #6980, #7228, #7693, #7731, #7997, #8046,
   #8054, #8056, #8060, #8063, #8064, #8068, #8072, #8091, #8095,
   #8096, #8098, #8106


Twisted Conch 15.5.0 (2015-11-18)
=================================

Features
--------
 - twisted.conch.ssh now supports the diffie-hellman-group-exchange-
   sha256 key exchange algorithm. (#7672)
 - twisted.conch.ssh now supports the diffie-hellman-group14-sha1 key
   exchange algorithm. (#7717)
 - twisted.conch.ssh.transport.SSHClientTransport now supports Diffie-
   Hellman key exchange using MSG_KEX_DH_GEX_REQUEST as described in
   RFC 4419. (#8100)
 - twisted.conch.ssh now supports the hmac-sha2-256 and hmac-sha2-512
   MAC algorithms. (#8108)

Deprecations and Removals
-------------------------
 - twisted.conch.ssh.keys.objectType is now deprecated. Use
   twisted.conch.ssh.keys.Key.sshType. (#8080)
 - twisted.conch.ssh.transport.SSHClientTransport no longer supports
   Diffie-Hellman key exchange using MSG_KEX_DH_GEX_REQUEST_OLD for
   pre RFC 4419 servers. (#8100)


Twisted Mail 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Names 15.5.0 (2015-11-18)
=================================

No significant changes have been made for this release.


Twisted News 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Pair 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Runner 15.5.0 (2015-11-18)
==================================

No significant changes have been made for this release.


Twisted Web 15.5.0 (2015-11-18)
================================

Features
--------
 - twisted.web.http.Request.addCookie now supports the httpOnly
   attribute which when set on cookies prevents the browser exposing
   it through channels other than HTTP and HTTPS requests (i.e. they
   will not be accessible through JavaScript). (#5911)
 - twisted.web.client.downloadPage is now ported to Python 3. (#6197)
 - twisted.web.client.Agent is now ported to Python 3. (#7407)
 - twisted.web.tap (ran when calling `twistd web`) has now been ported
   to Python 3. Not all features are enabled -- CGI, WSGI, and
   distributed web serving will be enabled in their respective tickets
   as they are ported. (#8008)

Bugfixes
--------
 - twisted.web.client.URI now supports IPv6 addresses. Previously this
   would mistake the colons used as IPv6 address group separators as
   the start of a port specification. (#7650)
 - twisted.web.util's failure template has been moved inline to work
   around Python 3 distribution issues. (#8047)
 - twisted.web.http.Request on Python 3 now handles multipart/form-
   data requests correctly. (#8052)

Other
-----
 - #8016, #8070


Twisted Words 15.5.0 (2015-11-18)
=================================

Features
--------
 - twisted.words.protocol.irc.IRC now has a sendCommand() method which
   can send messages with tags. (#6667)

Other
-----
 - #8015, #8097


Twisted Core 15.4.0 (2015-09-04)
================================

This is the last Twisted release where Python 2.6 is supported, on any
platform. 

Features
--------
 - Trial has been ported to Python 3. (#5965)
 - Twisted now requires setuptools for installation. (#7177)
 - twisted.internet.endpoints.clientFromString is now ported to Python
   3. (#7973)
 - twisted.internet._sslverify now uses SHA256 instead of MD5 for
   certificate request signing by default. (#7979)
 - twisted.internet.endpoints.serverFromString is now ported to Python
   3. (#7982)
 - twisted.positioning is now ported to Python 3. (#7987)
 - twisted.python.failure.Failure's __repr__ now includes the
   exception message. (#8004)

Bugfixes
--------
 - fixed a bug which could lead to a hang at shutdown in
   twisted.python.threadpool. (#2673)
 - twisted.internet.kqreactor on Python 3 now supports EINTR
   (Control-C) gracefully. (#7887)
 - Fix a bug introduced in 15.3.0; pickling a lambda function after
   importing twisted.persisted.styles raises PicklingError rather than
   AttributeError. (#7989)

Other
-----
 - #7902, #7980, #7990, #7992


Twisted Conch 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.

Other
-----
 - #7977


Twisted Mail 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Names 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.


Twisted News 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Pair 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Runner 15.4.0 (2015-09-04)
==================================

No significant changes have been made for this release.


Twisted Web 15.4.0 (2015-09-04)
===============================

Features
--------
 - twisted.web.proxy is now ported to Python 3. (#7939)
 - twisted.web.guard is now ported to Python 3. (#7974)

Bugfixes
--------
 - twisted.web.http.Request.setResponseCode now only allows bytes
   messages. (#7981)
 - twisted.web.server.Request.processingFailed will now correctly
   write out the traceback on Python 3. (#7996)


Twisted Words 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.


Twisted Core 15.3.0 (2015-08-04)
================================

Features
--------
 - twisted.application.app is now ported to Python 3 (#6914)
 - twisted.plugin now supports Python 3 (#7182)
 - twisted.cred.checkers is now ported to Python 3. (#7834)
 - twisted.internet.unix is now ported to Python 3. (#7874)
 - twisted.python.sendmsg has now been ported to Python 3, using the
   stdlib sendmsg/recvmsg functionality when available. (#7884)
 - twisted.internet.protocol.Factory now uses the new logging system
   (twisted.logger) for all its logging statements. (#7897)
 - twisted.internet.stdio is now ported to Python 3. (#7899)
 - The isDocker method has been introduced on
   twisted.python.runtime.Platform to detect if the running Python is
   inside a Docker container. Additionally, Platform.supportsINotify()
   now returns False if isDocker() is True, because of many Docker
   storage layers having broken INotify. (#7968)

Bugfixes
--------
 - twisted.logger.LogBeginner.beginLoggingTo now outputs the correct
   warning when it is called more than once. (#7916)

Deprecations and Removals
-------------------------
 - twisted.cred.pamauth (providing PAM support) has been removed due
   to it being unusable in current supported Python versions. (#3728)
 - twisted.application.app.HotshotRunner (twistd's hotshot profiler
   module) is removed and twistd now uses cProfile by default. (#5137)
 - twisted.python.win32.getProgramsMenuPath and
   twisted.python.win32.getProgramFilesPath are now deprecated.
   (#7883)
 - twisted.lore has now been removed, in preference to Sphinx. (#7892)
 - Deprecated zsh tab-complete files are now removed in preference to
   twisted.python.usage's tab-complete functionality. (#7898)
 - twisted.python.hashlib, deprecated since 13.1, has now been
   removed. (#7905)
 - twisted.trial.runner.DryRunVisitor, deprecated in Twisted 13.0, has
   now been removed. (#7919)
 - twisted.trial.util.getPythonContainers, deprecated since Twisted
   12.3, is now removed. (#7920)
 - Twisted no longer supports being packaged as subprojects. (#7964)

Other
-----
 - #6136, #7035, #7803, #7817, #7827, #7844, #7876, #7906, #7908,
   #7915, #7931, #7940, #7967, #7983


Twisted Conch 15.3.0 (2015-08-04)
=================================

Bugfixes
--------
 - The Conch Unix server now sets the HOME environment variable when
   executing commands. (#7936)

Other
-----
 - #7937


Twisted Mail 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Names 15.3.0 (2015-08-04)
=================================

No significant changes have been made for this release.


Twisted News 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Pair 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Runner 15.3.0 (2015-08-04)
==================================

No significant changes have been made for this release.


Twisted Web 15.3.0 (2015-08-04)
===============================

Features
--------
 - twisted.web.xmlrpc is now ported to Python 3. (#7795)
 - twisted.web.template and twisted.web.util are now ported to Python
   3. (#7811)
 - twisted.web.error is now ported to Python 3. (#7845)

Deprecations and Removals
-------------------------
 - twisted.web.html is now deprecated in favor of
   twisted.web.template. (#4948)

Other
-----
 - #7895, #7942, #7949, #7952, #7975


Twisted Words 15.3.0 (2015-08-04)
=================================

No significant changes have been made for this release.


Twisted Core 15.2.1 (2015-05-23)
================================

Bugfixes
--------
 - twisted.logger now marks the `isError` key correctly on legacy
   events generated by writes to stderr. (#7903)

Improved Documentation
----------------------
 - twisted.logger's documentation is now correctly listed in the table
   of contents. (#7904)


Twisted Conch 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted Lore 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Mail 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Names 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted News 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Pair 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Runner 15.2.1 (2015-05-23)
==================================

No significant changes have been made for this release.


Twisted Web 15.2.1 (2015-05-23)
===============================

No significant changes have been made for this release.


Twisted Words 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted Core 15.2.0 (2015-05-18)
================================

Features
--------
 - twisted.internet.process has now been ported to Python 3. (#5987)
 - twisted.cred.credentials is now ported to Python 3. (#6176)
 - twisted.trial.unittest.TestCase's assertEqual, assertTrue, and
   assertFalse methods now pass through the standard library's more
   informative failure messages. (#6306)
 - The new package twisted.logger provides a new, fully tested, and
   feature-rich logging framework. The old module twisted.python.log
   is now implemented using the new framework. The new logger HOWTO
   documents the new framework. (#6750)
 - twisted.python.modules is now ported to Python 3. (#7804)
 - twisted.python.filepath.FilePath now supports Unicode (text) paths.
   Like the os module, instantiating it with a Unicode path will
   return a Unicode-mode FilePath, instantiating with a bytes path
   will return a bytes-mode FilePath. (#7805)
 - twisted.internet.kqreactor is now ported to Python 3 (#7823)
 - twisted.internet.endpoints.ProcessEndpoint is now ported to Python
   3. (#7824)
 - twisted.python.filepath.FilePath now has asBytesMode and asTextMode
   methods which return a FilePath in the requested mode. (#7830)
 - twisted.python.components.proxyForInterface now creates method
   proxies that can be used with functools.wraps. (#7832)
 - The tls optional dependency will now also install the idna package
   to validate idna2008 names. (#7853)

Bugfixes
--------
 - Don't raise an exception if `DefaultLogObserver.emit()` gets an
   event with a message that raises when `repr()` is called on it.
   Specifically: use `textFromEventDict()` instead of a separate (and
   inferior) message rendering implementation. (#6569)
 - twisted.cred.credentials.DigestedCredentials incorrectly handled
   md5-sess hashing according to the RFC, which has now been fixed.
   (#7835)
 - Fixed an issue with twisted.internet.task.LoopingCall.withCount
   where sometimes the passed callable would be invoked with "0" when
   we got close to tricky floating point boundary conditions. (#7836)
 - twisted.internet.defer now properly works with the new logging
   system. (#7851)
 - Change `messages` key to `log_io` for events generated by
   `LoggingFile`. (#7852)
 - twisted.logger had literal characters in docstrings that are now
   quoted. (#7854)
 - twisted.logger now correctly formats a log event with a key named
   `message` when passed to a legacy log observer. (#7855)
 - twisted.internet.endpoints.HostnameEndpoint now uses getaddrinfo
   properly on Python 3.4 and above. (#7886)

Improved Documentation
----------------------
 - Fix a typo in narrative documentation for logger (#7875)

Deprecations and Removals
-------------------------
 - tkunzip and tapconvert in twisted.scripts were deprecated in 11.0
   and 12.1 respectively, and are now removed. (#6747)
 - twisted.protocols.gps is deprecated in preference to
   twisted.positioning. (#6810)
 - twisted.scripts.tap2deb and twisted.scripts.tap2rpm are now
   deprecated. (#7682)
 - twisted.trial.reporter.TestResult and
   twisted.trial.reporter.Reporter contained deprecated methods (since
   8.0) which have now been removed. (#7815)

Other
-----
 - #6027, #7287, #7701, #7727, #7758, #7776, #7786, #7812, #7819,
   #7831, #7838, #7865, #7866, #7869, #7872, #7877, #7878, #7885


Twisted Conch 15.2.0 (2015-05-18)
=================================

Features
--------
 - twisted.conch.ssh.forwarding now supports local->remote forwarding
   of IPv6 (#7751)


Twisted Lore 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Mail 15.2.0 (2015-05-18)
================================

Features
--------
 - twisted.mail.smtp.sendmail now uses ESMTP. It will
   opportunistically enable encryption and allow the use of
   authentication. (#7257)


Twisted Names 15.2.0 (2015-05-18)
=================================

No significant changes have been made for this release.


Twisted News 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Pair 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Runner 15.2.0 (2015-05-18)
==================================

No significant changes have been made for this release.


Twisted Web 15.2.0 (2015-05-18)
===============================

Features
--------
 - twisted.web.static is now ported to Python 3. (#6177)
 - twisted.web.server.Site accepts requestFactory as constructor
   argument. (#7016)

Deprecations and Removals
-------------------------
 - twisted.web.util had some HTML generation functions deprecated
   since 12.1 that have now been removed. (#7828)

Other
-----
 - #6927, #7797, #7802, #7846


Twisted Words 15.2.0 (2015-05-18)
=================================

Bugfixes
--------
 - The resumeOffset argument to
   twisted.words.protocol.irc.DccFileReceive now works as it is
   documented. (#7775)


Twisted Core 15.1.0 (2015-04-02)
================================

Features
--------
 - Optional dependencies can be installed using the extra_requires
   facility provided by setuptools. (#3696)

Improved Documentation
----------------------
 - Twisted Trial's basics documentation now has a link to the
   documentation about how Trial finds tests. (#4526)

Deprecations and Removals
-------------------------
 - twisted.application.internet.UDPClient, deprecated since Twisted
   13.1.0, has been removed. (#7702)

Other
-----
 - #6988, #7005, #7006, #7007, #7008, #7044, #7335, #7666, #7723,
   #7724, #7725, #7748, #7763, #7765, #7766, #7768


Twisted Conch 15.1.0 (2015-04-02)
=================================

No significant changes have been made for this release.


Twisted Lore 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Mail 15.1.0 (2015-04-02)
================================

Bugfixes
--------
 - twisted.mail.smtp.ESMTPClient now does not fall back to plain SMTP
   if authentication or TLS is required and not able to occur. (#7258)

Other
-----
 - #6705


Twisted Names 15.1.0 (2015-04-02)
=================================

No significant changes have been made for this release.

Other
-----
 - #7728


Twisted News 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Pair 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Runner 15.1.0 (2015-04-02)
==================================

No significant changes have been made for this release.

Other
-----
 - #7726


Twisted Web 15.1.0 (2015-04-02)
===============================

Features
--------
 - twisted.web.static.File allows defining a custom resource for
   rendering forbidden pages. (#6951)

Other
-----
 - #7000, #7485, #7750, #7762


Twisted Words 15.1.0 (2015-04-02)
=================================

Deprecations and Removals
-------------------------
 - twisted.words.protocols.msn is now deprecated (#6395)

Other
-----
 - #6494


Twisted Core 15.0.0 (2015-01-24)
================================

Features
--------
 - twisted.internet.protocol.ClientFactory (and subclasses) may now
   return None from buildProtocol to immediately close the connection.
   (#710)
 - twisted.trial.unittest.SynchronousTestCase.assertRaises can now
   return a context manager. (#5339)
 - Implementations of
   twisted.internet.interfaces.IStreamClientEndpoint included in
   Twisted itself will now handle None being returned from the client
   factory's buildProtocol method by immediately closing the
   connection and firing the waiting Deferred with a Failure. (#6976)
 - inlineCallbacks now supports using the return statement with a
   value on Python 3 (#7624)
 - twisted.spread.banana.Banana.sendEncoded() now raises a more
   informative error message if the user tries to encode objects of
   unsupported type. (#7663)

Bugfixes
--------
 - twisted.internet.interfaces.IReactorMulticast.listenMultiple works
   again RHEL 6's python 2.6. (#7159)
 - Allow much more of the code within Twisted to use ProcessEndpoint
   by adding IPushProducer and IConsumer interfaces to its resulting
   transport. (#7436)
 - twisted.internet.ssl.Certificate(...).getPublicKey().keyHash() now
   produces a stable value regardless of OpenSSL version.
   Unfortunately this means that it is different than the value
   produced by older Twisted versions. (#7651)
 - twisted.python.reflect.safe_str on Python 3 converts utf-8 encoded
   bytes to clean str instead of "b'a'" (#7660)
 - twisted.spread.banana.Banana now raises NotImplementedError when
   receiving pb messages without pb being the selected dialect (#7662)
 - The SSL server string endpoint parser
   (twisted.internet.endpoints.serverFromString) now constructs
   endpoints which, by default, disable the insecure SSLv3 protocol.
   (#7684)
 - The SSL client string endpoint parser
   (twisted.internet.endpoints.clientFromString) now constructs
   endpoints which, by default, disable the insecure SSLv3 protocol.
   (#7686)

Improved Documentation
----------------------
 - inlineCallbacks now has introductory documentation. (#1009)
 - The echoclient example now uses twisted.internet.task.react.
   (#7083)
 - Twisted Trial's how-to documentation now has a link to Twisted's
   contribution guidelines and has been reformatted. (#7475)
 - Fixed a path error in the make.bat file for building Sphinx
   documentation, so that it is now possible to build the documentation
   using make.bat on Windows. (#7542)

Deprecations and Removals
-------------------------
 - twisted.python.filepath.FilePath.statinfo was deprecated. (#4450)
 - twisted.internet.defer.deferredGenerator is now deprecated.
   twisted.internet.defer.inlineCallbacks should be used instead.
   (#6044)
 - Pickling twisted.internet.ssl.OptionSSLCertificationOptions and
   twisted.internet.ssl.Keypair is no longer supported. __getstate__
   and __setstate__ methods of these classes have been deprecated.
   (#6166)
 - twisted.spread.jelly's support for unjellying "instance" atoms is
   now deprecated. (#7653)

Other
-----
 - #3404, #4711, #5730, #6042, #6626, #6947, #6953, #6989, #7032,
   #7038, #7039, #7097, #7098, #7142, #7143, #7154, #7155, #7156,
   #7157, #7158, #7160, #7161, #7162, #7164, #7165, #7176, #7234,
   #7252, #7329, #7333, #7355, #7369, #7370, #7419, #7529, #7531,
   #7534, #7537, #7538, #7620, #7621, #7633, #7636, #7637, #7638,
   #7640, #7641, #7642, #7643, #7665, #7667, #7713, #7719


Twisted Conch 15.0.0 (2015-01-24)
=================================

Features
--------
 - The new APIs: twisted.conch.checkers.IAuthorizedKeysDB,
   twisted.conch.checkers.InMemorySSHKeyDB,
   twisted.conch.checkers.UNIXAuthorizedKeyFiles, and
   twisted.conch.checkers.SSHPublicKeyChecker have been added to
   provide functionality to check the validity of SSH public keys and
   specify where authorized keys are to be found. (#7144)

Deprecations and Removals
-------------------------
 - twisted.conch.checkers.SSHPublicKeyDatabase is now deprecated in
   favor of a twisted.conch.checkers.SSHPublicKeyChecker instantiated
   with a twisted.conch.checkers.UNIXAuthorizedKeyFiles. (#7144)

Other
-----
 - #6626, #7002, #7526, #7532, #7698


Twisted Lore 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.


Twisted Mail 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #6999, #7708


Twisted Names 15.0.0 (2015-01-24)
=================================

Bugfixes
--------
 - twisted.names.secondary.SecondaryAuthority can now answer queries
   again (broken since 13.2.0). (#7408)

Other
-----
 - #7352


Twisted News 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #7703


Twisted Pair 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #7722


Twisted Runner 15.0.0 (2015-01-24)
==================================

No significant changes have been made for this release.


Twisted Web 15.0.0 (2015-01-24)
===============================

Features
--------
 - twisted.web.client.Agent.usingEndpointFactory allows creating an
   Agent that connects in non-standard ways, e.g. via a proxy or a
   UNIX socket. (#6634)
 - The Deferred returned by twisted.web.client.readBody can now be
   cancelled. (#6686)

Deprecations and Removals
-------------------------
 - twisted.web.iweb.IRequest.getClient is now deprecated.  Its
   implementation in Twisted, twisted.web.http.Request.getClient, is
   also deprecated and will no longer attempt to resolve the client IP
   address to a hostname. (#2252)

Other
-----
 - #7247, #7302, #7680, #7689


Twisted Words 15.0.0 (2015-01-24)
=================================

No significant changes have been made for this release.

Other
-----
 - #6994, #7163, #7622


Twisted Core 14.0.2 (2014-09-18)
================================

No significant changes have been made for this release.


Twisted Conch 14.0.2 (2014-09-18)
=================================

No significant changes have been made for this release.


Twisted Lore 14.0.2 (2014-09-18)
================================

No significant changes have been made for this release.


Twisted Mail 14.0.2 (2014-09-18)
================================

No significant changes have been made for this release.


Twisted Names 14.0.2 (2014-09-18)
=================================

No significant changes have been made for this release.


Twisted News 14.0.2 (2014-09-18)
================================

No significant changes have been made for this release.


Twisted Pair 14.0.2 (2014-09-18)
================================

No significant changes have been made for this release.


Twisted Runner 14.0.2 (2014-09-18)
==================================

No significant changes have been made for this release.


Twisted Web 14.0.2 (2014-09-18)
===============================

No significant changes have been made for this release.


Twisted Words 14.0.2 (2014-09-18)
=================================

No significant changes have been made for this release.


Twisted Core 14.0.1 (2014-09-17)
================================

No significant changes have been made for this release.


Twisted Conch 14.0.1 (2014-09-17)
=================================

No significant changes have been made for this release.


Twisted Lore 14.0.1 (2014-09-17)
================================

No significant changes have been made for this release.


Twisted Mail 14.0.1 (2014-09-17)
================================

No significant changes have been made for this release.


Twisted Names 14.0.1 (2014-09-17)
=================================

No significant changes have been made for this release.


Twisted News 14.0.1 (2014-09-17)
================================

No significant changes have been made for this release.


Twisted Pair 14.0.1 (2014-09-17)
================================

No significant changes have been made for this release.


Twisted Runner 14.0.1 (2014-09-17)
==================================

No significant changes have been made for this release.


Twisted Web 14.0.1 (2014-09-17)
===============================

Bugfixes
--------
 - BrowserLikePolicyForHTTPS would always ignore the specified
   trustRoot and use the system trust root instead, which has been
   rectified. (#7647)


Twisted Words 14.0.1 (2014-09-17)
=================================

No significant changes have been made for this release.


Twisted Core 14.0.0 (2014-05-08)
================================

Features
--------
 - twisted.internet.interfaces.IUDPTransport - and that interface's
   implementations in Twisted - now supports enabling broadcasting.
   (#454)
 - trial's TestCase will now report a test method as an error if that
   test method is a generator function, preventing an issue when a
   user forgets to decorate a test method with defer.inlineCallbacks,
   causing the test method to not run. (#3917)
 - twisted.positioning, a new API for positioning systems such as GPS,
   has been added. It comes with an implementation of NMEA, the most
   common wire protocol for GPS devices. It will supersede
   twisted.protoocols.gps. (#3926)
 - The new interface twisted.internet.interfaces.IStreamClientEndpoint
   StringParserWithReactor will supply the reactor to its
   parseStreamClient method, passed along from
   twisted.internet.endpoints.clientFromString. (#5069)
 - IReactorUDP.listenUDP, IUDPTransport.write and
   IUDPTransport.connect now accept ipv6 address literals. (#5086)
 - A new API, twisted.internet.ssl.optionsForClientTLS, allows clients
   to specify and verify the identity of the peer they're communicating
   with.  When used with the service_identity library from PyPI, this
   provides support for service identity verification from RFC 6125, as
   well as server name indication from RFC 6066. (#5190)
 - Twisted's TLS support now provides a way to ask for user-configured
   trust roots rather than having to manually configure such
   certificate authority certificates yourself.
   twisted.internet.ssl.CertificateOptions now accepts a new argument,
   trustRoot, which combines verification flags and trust sources, as
   well as a new function that provides a value for that argument,
   twisted.internet.ssl.platformTrust, which allows using the trusted
   platform certificate authorities from OpenSSL for certificate
   verification. (#5446)
 - Constants are now comparable/orderable based on the order in which
   they are defined. (#6523)
 - "setup.py install" and "pip install" now work on Python 3.3,
   installing the subset of Twisted that has been ported to Python 3.
   (#6539)
 - twisted.internet.ssl.CertificateOptions now supports ECDHE for
   servers by default on pyOpenSSL 0.14 and later, if the underlying
   versions of cryptography.io and OpenSSL support it. (#6586)
 - twisted.internet.ssl.CertificateOptions now allows the user to set
   acceptable ciphers and uses secure ones by default. (#6663)
 - The Deferred returned by
   twisted.internet.defer.DeferredFilesystemLock.deferUntilLocked can
   now be cancelled. (#6720)
 - twisted.internet.ssl.CertificateOptions now enables TLSv1.1 and
   TLSv1.2 by default (in addition to TLSv1.0) if the underlying
   version of OpenSSL supports these protocol versions. (#6772)
 - twisted.internet.ssl.CertificateOptions now supports Diffie-Hellman
   key exchange. (#6799)
 - twisted.internet.ssl.CertificateOptions now disables TLS
   compression to avoid CRIME attacks and, for servers, uses server
   preference to choose the cipher. (#6801)
 - SSL server endpoint string descriptions now support the
   specification of Diffie-Hellman key exchange parameter files.
   (#6924)
 - twisted.python.reflect.requireModule was added to handle
   conditional imports of python modules and work around pyflakes
   warnings of unused imports code. (#7014)

Bugfixes
--------
 - If a ProcessProtocol.processExited method raised an exception a
   broken process handler would be left in the global process state
   leading to errors later on. This has been fixed and now an error
   will be logged instead. (#5151)
 - Twisted now builds on Solaris. Note that lacking a Buildbot slave
   (see http://buildbot.twistedmatrix.com/boxes-supported) Solaris is
   not a supported Twisted platform. (#5728)
 - twisted.internet.utils is now correctly installed on Python 3.
   (#6929)
 - twisted.python.threadpool.ThreadPool no longer starts new workers
   when its pool size is changed while the pool is not running.
   (#7011)

Improved Documentation
----------------------
 - Twisted now uses the Sphinx documentation generator for its
   narrative documentation, which means that the source format for
   narrative documentation has been converted to ReStructuredText.
   (#4500)
 - The Sphinx documentation is now also configured to allow
   intersphinx links to standard library documentation. (#4582)
 - The docstring for twisted.internet.task.react now better documents
   the main parameter (#6071)
 - The writing standard now explicitly mandates the usage of
   ungendered pronouns. (#6858)

Deprecations and Removals
-------------------------
 - test_import.py was removed as it was redundant. (#2053)
 - Support for versions of pyOpenSSL older than 0.10 has been removed.
   Affected users should upgrade pyOpenSSL. (#5014)
 - twisted.internet.interfaces.IStreamClientEndpointStringParser is
   now deprecated in favor of twisted.internet.interfaces.IStreamClien
   tEndpointStringParserWithReactor. (#5069)
 - unsignedID and setIDFunction, previously part of
   twisted.python.util and deprecated since 13.0, have now been
   removed. (#6707)
 - FTPClient.changeDirectory was deprecated in 8.2 and is now removed.
   (#6759)
 - twisted.internet.stdio.StandardIO.closeStdin, an alias for
   loseWriteConnection only available on POSIX and deprecated since
   2.1, has been removed. (#6785)
 - twisted.python.reflect.getcurrent is now deprecated and must not be
   used. twisted.python.reflect.isinst is now deprecated in favor of
   the built-in isinstance. (#6859)

Other
-----
 - #1822, #5929, #6239, #6537, #6565, #6614, #6632, #6690, #6784,
   #6792, #6795, #6821, #6843, #6846, #6854, #6856, #6857, #6872,
   #6892, #6902, #6906, #6922, #6926, #6936, #6941, #6942, #6943,
   #6944, #6945, #6946, #6948, #6979, #7001, #7049, #7051, #7094,
   #7098


Twisted Conch 14.0.0 (2014-05-08)
=================================

Improved Documentation
----------------------
 - The docstring for twisted.conch.ssh.userauth.SSHUserAuthClient is
   now clearer on how the preferredOrder instance variable is handled.
   (#6850)

Other
-----
 - #6696, #6807, #7054


Twisted Lore 14.0.0 (2014-05-08)
================================

Deprecations and Removals
-------------------------
 - twisted.lore is now deprecated in favor of Sphinx. (#6907)

Other
-----
 - #6998


Twisted Mail 14.0.0 (2014-05-08)
================================

Improved Documentation
----------------------
 - twisted.mail.alias now has full API documentation. (#6637)
 - twisted.mail.tap now has full API documentation. (#6648)
 - twisted.mail.maildir now has full API documentation. (#6651)
 - twisted.mail.pop3client now has full API documentation. (#6653)
 - twisted.mail.protocols now has full API documentation.  (#6654)
 - twisted.mail.pop now has full API documentation. (#6666)
 - twisted.mail.relay and twisted.mail.relaymanager now have full API
   documentation. (#6739)
 - twisted.mail.pop3client public classes now appear as part of the
   twisted.mail.pop3 API. (#6761)

Other
-----
 - #6696


Twisted Names 14.0.0 (2014-05-08)
=================================

Features
--------
 - twisted.names.root.Resolver now accepts a resolverFactory argument,
   which makes it possible to control how root.Resolver performs
   iterative queries to authoritative nameservers. (#6095)
 - twisted.names.dns.Message now has a repr method which shows only
   those instance flags, fields and sections which are set to non-
   default values. (#6847)
 - twisted.names.dns.Message now support rich comparison. (#6848)

Bugfixes
--------
 - twisted.names.server.DNSServerFactory now responds with messages
   whose flags and fields are reset to their default values instead of
   copying these from the request. This means that AD and CD flags,
   and EDNS OPT records in the request are no longer mirrored back to
   the client. (#6645)

Improved Documentation
----------------------
 - twisted.names now has narrative documentation showing how to create
   a custom DNS server. (#6864)
 - twisted.names.server now has full API documentation. (#6886)
 - twisted.names now has narrative documentation explaining how to use
   its client APIs. (#6925)
 - twisted.names now has narrative documentation and examples showing
   how to perform reverse DNS lookups. (#6969)

Other
-----
 - #5675, #6222, #6672, #6696, #6887, #6940, #6975, #6990


Twisted News 14.0.0 (2014-05-08)
================================

No significant changes have been made for this release.

Other
-----
 - #6991


Twisted Pair 14.0.0 (2014-05-08)
================================

Features
--------
 - twisted.pair.tuntap now has complete test coverage, basic
   documentation, and works without the difficult-to-find system
   bindings it used to require. (#6169)

Other
-----
 - #6898, #6931, #6993


Twisted Runner 14.0.0 (2014-05-08)
==================================

No significant changes have been made for this release.

Other
-----
 - #6992


Twisted Web 14.0.0 (2014-05-08)
===============================

Features
--------
 - twisted.web.http.proxiedLogFormatter can now be used with
   twisted.web.http.HTTPFactory (and subclasses) to record X
   -Forwarded-For values to the access log when the HTTP server is
   deployed behind a reverse proxy. (#1468)
 - twisted.web.client.Agent now uses
   twisted.internet.ssl.CertificateOptions for SSL/TLS and benefits
   from its continuous improvements. (#6893)

Bugfixes
--------
 - twisted.web.client.Agent now correctly manage flow-control on
   pooled connections, and therefore requests will no longer hang
   sometimes when deliverBody is not called synchronously within the
   callback on Request. (#6751)
 - twisted.web.client.Agent now verifies that the provided server
   certificate in a TLS connection is trusted by the platform. (#7042)
 - When requesting an HTTPS URL with twisted.web.client.Agent, the
   hostname of the presented certificate will be checked against the
   requested hostname; mismatches will now result in an error rather
   than a man-in-the-middle opportunity for attackers.  This may break
   existing code that incorrectly depended on insecure behavior, but
   such code was erroneous and should be updated.  (#4888)

Other
-----
 - #5004, #6881, #6956


Twisted Words 14.0.0 (2014-05-08)
=================================

Bugfixes
--------
 - twisted.words.protocols.jabber.sasl_mechansisms.DigestMD5 now works
   with unicode arguments. (#5066)

Other
-----
 - #6696


Twisted Core 13.2.0 (2013-10-29)
================================

Features
--------
 - twistd now waits for the application to start successfully before
   exiting after daemonization. (#823)
 - twisted.internet.endpoints now provides HostnameEndpoint, a TCP
   client endpoint that connects to a hostname as quickly as possible.
   (#4859)
 - twisted.internet.interfaces.IReactorSocket now has a new
   adoptDatagramPort method which is implemented by some reactors
   allowing them to listen on UDP sockets set up by external software
   (eg systemd or launchd). (#5574)
 - trial now accepts an --order option that specifies what order to
   run TestCase methods in. (#5787)
 - Port twisted.python.lockfile to Python 3, enabling
   twisted.python.defer.DeferredFilesystemLock and tests. (#5960)
 - Returning a Deferred from a callback that's directly returned from
   that Deferred will now produce a DeprecationWarning, to notify
   users of the buggy behavior. (#6164)
 - SSL server endpoint string descriptions now support the
   specification of chain certificates. (#6499)
 - twisted.application.reactors.installReactor now returns the just-
   installed reactor. (#6596)
 - twisted.internet.defer.DeferredList now has a new cancel method.
   And twisted.internet.defer.gatherResults now returns a cancellable
   result. (#6639)

Bugfixes
--------
 - twisted.protocols.basic.LineReceiver no longer passes incorrect
   data (a buffer missing a delimiter) to lineLengthExceeded in
   certain cases. (#6536)
 - twisted.cred.digest.DigestCredentialFactory now supports decoding
   challenge responses with field values including ",". (#6609)
 - twisted.internet.endpoints.TCP6ClientEndpoint now establishes
   connections when constructed with a hostname. (#6633)
 - twisted.application.internet.TimerService is now pickleable in all
   cases. (#6657)

Improved Documentation
----------------------
 - The howto document page of Deferred now has documentation about
   cancellation. (#4320)
 - Docstrings for twisted.internet.task.Cooperator and cooperate.
   (#6213)

Deprecations and Removals
-------------------------
 - Returning a Deferred from a callback that's directly returned from
   that Deferred will now produce a DeprecationWarning, to notify
   users of the buggy behavior. (#6164)
 - Accessor, AccessorType, OriginalAccessor, PropertyAccessor,
   Settable and Summer in twisted.python.reflect, deprecated since
   Twisted 12.1.0, are now removed. (#6689)

Other
-----
 - #5001, #5312, #5387, #5442, #5634, #6221, #6393, #6406, #6485,
   #6570, #6575, #6610, #6674, #6684, #6685, #6715, #6729, #6731,
   #6736, #6773, #6788, #6793


Twisted Conch 13.2.0 (2013-10-29)
=================================

Features
--------
 - ckeygen now accepts --no-passphrase to generate unprotected keys.
   (#5998)
 - twisted.conch.endpoints.SSHCommandClientEndpoint.newConnection now
   supplies a convenient default for the `ui` parameter if a value is
   not passed in for it. (#6550)

Bugfixes
--------
 - ckeygen --changepass now doesn't delete unencrypted keys or raise
   an exception on encrypted ones. (#5894)
 - twisted.conch.endpoints.SSHCommandClientEndpoint now doesn't try
   password authentication if there is no password specified. (#6553)
 - twisted.conch.endpoints.SSHCommandClientEndpoint now uses the
   standard SSH port if no port is specified. (#6631)

Other
-----
 - #5387, #6220


Twisted Lore 13.2.0 (2013-10-29)
================================

No significant changes have been made for this release.

Other
-----
 - #6546


Twisted Mail 13.2.0 (2013-10-29)
================================

Features
--------
 - twisted.mail.smtp.sendmail now returns a cancellable Deferred.
   (#6572)

Improved Documentation
----------------------
 - twisted.mail.mail now has full API documentation. (#6649)
 - twisted.mail.bounce now has full API documentation. (#6652)

Other
-----
 - #5387, #6486


Twisted Names 13.2.0 (2013-10-29)
=================================

Features
--------
 - twisted.names.authority.FileAuthority now considers any AAAA it
   knows about for inclusion in the additional section of a response
   (following the same logic previously used for including A records
   there). (#6642)
 - twisted.names.dns.Message now allows encoding and decoding of the
   Authentic Data (AD) and Checking Disabled (CD) flags described in
   RFC2535. (#6680)

Bugfixes
--------
 - twisted.names.resolve.ResolverChain now returns a
   twisted.names.error.DomainError failure if its resolvers list is
   empty. (#5992)
 - twisted.names.authority.FileAuthority now only returns
   AuthoritativeDomainError (NXDOMAIN) for names which are subdomains.
   (#6475)
 - The Deferred returned by twisted.names.client.Resolver.queryTCP now
   fires with an error if the TCP connection attempt fails. (#6658)

Improved Documentation
----------------------
 - Use zope.interface.moduleProvides to allow pydoctor to properly
   document the twisted.names.client.lookup* functions. (#6328)

Other
-----
 - #5387, #5668, #6563, #6655


Twisted News 13.2.0 (2013-10-29)
================================

No significant changes have been made for this release.


Twisted Pair 13.2.0 (2013-10-29)
================================

No significant changes have been made for this release.


Twisted Runner 13.2.0 (2013-10-29)
==================================

No significant changes have been made for this release.


Twisted Web 13.2.0 (2013-10-29)
===============================

Features
--------
 - IAgent has been added to twisted.web.iweb to explicitly define the
   interface implemented by the various "Agent" classes in
   twisted.web.client. (#6702)

Bugfixes
--------
 - twisted.web.client.Response.deliverBody now calls connectionLost on
   the body protocol for responses with no body (such as 204, 304, and
   HEAD requests). (#5476)
 - twisted.web.static.loadMimeTypes now uses all available system MIME
   types. (#5717)

Deprecations and Removals
-------------------------
 - Two attributes of twisted.web.iweb.IRequest, headers and
   received_headers, are now deprecated. (#6704)

Other
-----
 - #5387, #6119, #6121, #6695, #6701, #6734


Twisted Words 13.2.0 (2013-10-29)
=================================

Bugfixes
--------
 - twisted.words.service.IRCUser now properly reports an error, in
   response to NICK commands with non-UTF8 and non-ASCII symbols.
   (#5780)

Other
-----
 - #5329, #5387, #6544


Twisted Core 13.1.0 (2013-06-23)
================================

Features
--------
 - trial now has an --exitfirst flag which stops the test run after
   the first error or failure. (#1518)
 - twisted.internet.ssl.CertificateOptions now supports chain
   certificates. (#2061)
 - twisted.internet.endpoints now provides ProcessEndpoint, a child
   process endpoint. (#4696)
 - Factory now has a forProtocol classmethod that constructs an
   instance and sets its protocol attribute. (#5016)
 - twisted.internet.endpoints.connectProtocol allows connecting to a
   client endpoint using only a protocol instance, rather than
   requiring a factory. (#5270)
 - twisted.trial.unittest.SynchronousTestCase.assertNoResult no longer
   swallows the result, if the assertion succeeds. (#6291)
 - twisted.python.constants.FlagConstant implements __iter__ so that
   it can be iterated upon to find the flags that went into a flag
   set, and implements __nonzero__ to test as false when empty.
   (#6302)
 - assertIs and assertIsNot have now been added to
   twisted.trial.unittest.TestCase. (#6350)
 - twisted.trial.unittest.TestCase.failureResultOf now takes an
   optional expected failure type argument. (#6380)
 - The POSIX implementation of
   twisted.internet.interfaces.IReactorProcess now does not change the
   parent process UID or GID in order to run child processes with a
   different UID or GID. (#6443)

Bugfixes
--------
 - self.transport.resumeProducing() will no longer raise an
   AssertionError if called after self.transport.loseConnection()
   (#986)
 - twisted.protocols.ftp.FTP now supports IFTPShell implementations
   which return non-ASCII filenames as unicode strings. (#5411)
 - twisted.internet.ssl.CertificateOptions now disables SSLv2 if
   SSLv23 is selected, allowing only SSLv3 and TLSv1. (#6337)
 - trial dist support now gets sys.path from an environment variable
   passed to it. (#6390)
 - twisted.test.proto_helpers.StringTransportWithDisconnection now
   correctly passes Failure instead of an exception to
   connectionLost through loseConnection. (#6521)

Improved Documentation
----------------------
 - The Application howto now provides an example of writing a custom
   Service. (#5586)
 - The -j flag to trial (introduced in 12.3.0) is now documented.
   (#5994)
 - The SSL howto now covers twisted.internet.ssl.CertificateOptions
   instead of the older context factories it replaces. (#6273)
 - The Constants HOWTO documents iteration and truth testing of flags,
   as well as previously undocumented boolean operations. (#6302)

Deprecations and Removals
-------------------------
 - twisted.trial.runner.suiteVisit and PyUnitTestCase as well as
   visitor methods, all deprecated since Twisted 8.0, have been
   removed. (#3231)
 - twisted.python._epoll bindings were removed; the epoll reactor now
   uses the stdlib-provided epoll support. (#5847)
 - The deprecated LENGTH, DATA, COMMA, and NUMBER NetstringReceiver
   parser state attributes in t.protocols.basic are removed now.
   (#6321)
 - twisted.trial.runner.DryRunVisitor is now deprecated. Trial uses a
   different method to handle --dry-run now. (#6333)
 - twisted.python.hashlib is now deprecated in favor of hashlib from
   stdlib. (#6342)
 - twisted.web.server's Session.loopFactory, lifetime parameter of
   Session.startCheckingExpiration and Session.checkExpired attributes,
   deprecated since Twisted 9.0, have been removed. (#6514)

Other
-----
 - #2380, #5197, #5228, #5386, #5459, #5578, #5801, #5952, #5955,
   #5981, #6051, #6189, #6228, #6240, #6284, #6286, #6299, #6316,
   #6353, #6354, #6368, #6377, #6378, #6381, #6389, #6400, #6403,
   #6407, #6416, #6417, #6418, #6419, #6430, #6433, #6438, #6439,
   #6440, #6441, #6444, #6459, #6465, #6468, #6477, #6480, #6498,
   #6508, #6510, #6525


Twisted Conch 13.1.0 (2013-06-23)
=================================

Features
--------
 - twisted.conch.endpoints.SSHCommandClientEndpoint is a new
   IStreamClientEndpoint which supports connecting a protocol to the
   stdio of a command running on a remote host via an SSH connection.
   (#4698)
 - twisted.conch.client.knownhosts.KnownHostsFile now has a public
   `savePath` attribute giving the filesystem path where the known
   hosts data is saved to and loaded from. (#6255)
 - twisted.conch.endpoints.SSHCommandClientEndpoint.connect() returns
   a cancellable Deferred when using new connections. (#6532)

Other
-----
 - #5386, #6342, #6386, #6405, #6541


Twisted Lore 13.1.0 (2013-06-23)
================================

Deprecations and Removals
-------------------------
 - twisted.lore.lint.parserErrors is deprecated now. (#5386)


Twisted Mail 13.1.0 (2013-06-23)
================================

Bugfixes
--------
 - twisted.mail.smtp.ESMTPClient no longer tries to use a STARTTLS
   capability offered by a server after TLS has already been
   negotiated. (#6524)

Deprecations and Removals
-------------------------
 - twisted.mail.IDomain.startMessage, deprecated since 2003, is
   removed now. (#4151)

Other
-----
 - #6342


Twisted Names 13.1.0 (2013-06-23)
=================================

No significant changes have been made for this release.

Other
-----
 - #3908, #6381


Twisted News 13.1.0 (2013-06-23)
================================

No significant changes have been made for this release.

Other
-----
 - #6342


Twisted Pair 13.1.0 (2013-06-23)
================================

No significant changes have been made for this release.


Twisted Runner 13.1.0 (2013-06-23)
==================================

No significant changes have been made for this release.


Twisted Web 13.1.0 (2013-06-23)
===============================

Features
--------
 - The deferred returned by twisted.web.client.Agent.request can now
   be cancelled. (#4330)
 - twisted.web.client.BrowserLikeRedirectAgent, a new redirect agent,
   treats HTTP 301 and 302 like HTTP 303 on non-HEAD/GET requests,
   changing the method to GET before proceeding. (#5434)
 - The new attribute twisted.web.iweb.IResponse.request is a reference
   to a provider of the new twisted.web.iweb.IClientRequest interface
   which, among other things, provides a way to access the request's
   absolute URI. It is now also possible to inspect redirect history
   with twisted.web.iweb.IResponse.previousResponse. (#5435)
 - twisted.web.client.RedirectAgent now supports relative URI
   references in the Location HTTP header. (#5462)
 - twisted.web.client now provides readBody to collect the body of a
   response from Agent into a string. (#6251)

Bugfixes
--------
 - twisted.web.xmlrpc.QueryProtocol now generates valid Authorization
   headers for long user names and passwords. (#2980)

Other
-----
 - #6122, #6153, #6342, #6381, #6391, #6503


Twisted Words 13.1.0 (2013-06-23)
=================================

Features
--------
 - twisted.words.protocols.irc.assembleFormattedText flattens a
   formatting structure into mIRC-formatted markup; conversely
   twisted.words.protocols.irc.stripFormatting removes all mIRC
   formatting from text. (#3844)

Deprecations and Removals
-------------------------
 - The `crippled` attribute in
   twisted.words.protocols.jabber.xmpp_stringprep is deprecated now.
   (#5386)

Other
-----
 - #6315, #6342, #6392, #6402, #6479, #6481, #6482


Twisted Core 13.0.0 (2013-03-19)
================================

Features
--------
 - The twisted.protocols.ftp.FTP server now treats "LIST -La", "LIST
   -al", and all other combinations of ordering and case of the "-l"
   and "-a" flags the same: by ignoring them rather than treating them
   as a pathname. (#1333)
 - twisted.python.log.FileLogObserver now uses `datetime.strftime` to
   format timestamps, adding support for microseconds and timezone
   offsets to the `timeFormat` string. (#3513)
 - trial now deterministically runs tests in the order in which they
   were specified on the command line, instead of quasi-randomly
   according to dictionary key ordering. (#5520)
 - Cooperator.running can be used to determine the current cooperator
   status. (#5937)
 - twisted.python.modules.PythonPath now implements `__contains__` to
   allow checking, by name, whether a particular module exists within
   it. (#6198)
 - twisted.application.internet.TimerService.stopService now waits for
   any currently running call to finish before firing its deferred.
   (#6290)

Bugfixes
--------
 - twisted.protocols.ftp.FTP now recognizes all glob expressions
   supported by fnmatch. (#4181)
 - Constant values defined using twisted.python.constants can now be
   set as attributes of other classes without triggering an unhandled
   AttributeError from the constants implementation. (#5797)
 - Fixed problem where twisted.names.client.Resolver was not closing
   open file handles which can lead to an out of file descriptor error
   on PyPy. (#6216)
 - All reactors included in Twisted itself now gracefully handle a
   rare case involving delayed calls scheduled very far in the future.
   (#6259)
 - twisted.trial.reporter.Reporter._trimFrames correctly removes
   frames from twisted.internet.utils.runWithWarningsSuppressed again,
   after being broke in #6009. (#6282)

Improved Documentation
----------------------
 - A new "Deploying Twisted with systemd" howto document which
   demonstrates how to start a Twisted service using systemd socket
   activation. (#5601)
 - New "Introduction to Deferreds" howto.  Old howto rebranded as
   reference documentation. (#6180)
 - "Components: Interfaces and Adapters" howto now uses
   zope.interface's decorator-based API. (#6269)

Deprecations and Removals
-------------------------
 - twisted.python.util.unsignedID and setIDFunction are deprecated
   now. (#5544)
 - twisted.python.zshcomp deprecated since 11.1.0 has now been
   removed. Shell tab-completion is now handled by
   twisted.python.usage. (#5767)
 - python.runtime.Platform.isWinNT is deprecated now. Use
   Platform.isWindows instead. (#5925)
 - twisted.trial.util.findObject, deprecated since Twisted 10.1.0, has
   been removed. (#6260)

Other
-----
 - #2915, #4009, #4315, #5909, #5918, #5953, #6026, #6046, #6165,
   #6201, #6207, #6208, #6211, #6235, #6236, #6247, #6265, #6272,
   #6288, #6297, #6309, #6322, #6323, #6324, #6327, #6332, #6338,
   #6349


Twisted Conch 13.0.0 (2013-03-19)
=================================

Features
--------
 - twisted.conch.client.knownhosts.KnownHostsFile now takes care not
   to overwrite changes to its save file made behind its back, making
   it safer to use with the same known_hosts file as is being used by
   other software. (#6256)

Other
-----
 - #5864, #6257, #6297


Twisted Lore 13.0.0 (2013-03-19)
================================

No significant changes have been made for this release.


Twisted Mail 13.0.0 (2013-03-19)
================================

Bugfixes
--------
 - twisted.mail.smtp.ESMTPClient no longer attempts to negotiate a TLS
   session if transport security has been requested and the protocol
   is already running on a TLS connection. (#3989)
 - twisted.mail.imap4.Query now filters illegal characters from the
   values of KEYWORD and UNKEYWORD and also emits them without adding
   quotes (which are also illegal). (#4392)
 - twisted.mail.imap4.IMAP4Client can now interpret the BODY response
   for multipart/* messages with parts which are also multipart/*.
   (#4631)

Deprecations and Removals
-------------------------
 - tlsMode attribute of twisted.mail.smtp.ESMTPClient is deprecated.
   (#5852)

Other
-----
 - #6218, #6297


Twisted Names 13.0.0 (2013-03-19)
=================================

Features
--------
 - twisted.names.dns.Name and twisted.names.srvconnect.SRVConnector
   now support unicode domain names, automatically converting using
   the idna encoding. (#6245)

Improved Documentation
----------------------
 - The API documentation for IResolver and its implementations has
   been updated and consolidated in
   twisted.internet.interfaces.IResolver. (#4685)

Deprecations and Removals
-------------------------
 - The retry, Resolver.discoveredAuthority, lookupNameservers,
   lookupAddress, extractAuthority, and discoverAuthority APIs in
   twisted.names.root have been deprecated since 10.0 and have been
   removed.  (#5564)

Other
-----
 - #5596, #6246, #6297


Twisted News 13.0.0 (2013-03-19)
================================

No significant changes have been made for this release.


Twisted Pair 13.0.0 (2013-03-19)
================================

No significant changes have been made for this release.


Twisted Runner 13.0.0 (2013-03-19)
==================================

No significant changes have been made for this release.

Other
-----
 - #5740


Twisted Web 13.0.0 (2013-03-19)
===============================

Bugfixes
--------
 - twisted.web.template now properly quotes attribute values,
   including Tag instances serialized within attribute values. (#6275)

Other
-----
 - #6167, #6297, #6326


Twisted Words 13.0.0 (2013-03-19)
=================================

Bugfixes
--------
 - twisted.words.im.ircsupport no longer logs a failure whenever
   receiving ISUPPORT messages from an IRC server. (#6263)

Other
-----
 - #6297


Twisted Core 12.3.0 (2012-12-20)
================================

Features
--------
 - The new -j flag to trial provides a trial runner supporting
   multiple worker processes on the local machine, for parallel
   testing. (#1784)
 - twisted.internet.task.react, a new function, provides a simple API
   for running the reactor until a single asynchronous function
   completes. (#3270)
 - twisted.protocols.ftp.FTP now handles FEAT and OPTS commands.
   (#4515)
 - trial now supports specifying a debugger other than pdb with the
   --debugger command line flag. (#5794)
 - twisted.python.util.runWithWarningsSuppressed has been added; it
   runs a function with specified warning filters. (#5950)
 - trial's skipping feature is now implemented in a way compatible with the
   standard library unittest's runner. (#6006)
 - The setup3.py script is now provided to provisionally support
   building and installing an experimental, incomplete version of
   Twisted in a Python 3 environment. (#6040)
 - twisted.python.util.FancyStrMixin now supports arbitrary callables
   to format attribute values. (#6063)
 - Several new methods of twisted.trial.unittest.SynchronousTestCase
   - `successResultOf`, `failureResultOf`, and `assertNoResult` -
   have been added to make testing `Deferred`-using code easier.
   (#6105)

Bugfixes
--------
 - twisted.protocols.basic.LineReceiver now does not hit the maximum
   stack recursion depth when the line and data mode is switched many
   times. (#3050)
 - twisted.protocols.ftp.FTPFileListProtocol fixed to support files
   with space characters in their name. (#4986)
 - gireactor and gtk3reactor no longer prevent gi.pygtkcompat from
   working, and likewise can load if gi.pygtkcompat has previously
   been enabled. (#5676)
 - gtk2reactor now works again on FreeBSD, and perhaps other platforms
   that were broken by gi interactions. (#5737)
 - gireactor now works with certain older versions of gi that are
   missing the threads_init() function. (#5790)
 - Fixed a bug where twisted.python.sendmsg would sometimes fail with
   obscure errors including "Message too long" or "Invalid argument"
   on some 64-bit platforms. (#5867)
 - twisted.internet.endpoints.TCP6ClientEndpoint now provides
   twisted.internet.interfaces.IStreamClientEndpoint (#5876)
 - twisted.internet.endpoints.AdoptedStreamServerEndpoint now provides
   twisted.internet.interfaces.IStreamServerEndpoint. (#5878)
 - Spawning subprocesses with PTYs now works on OS X 10.8. (#5880)
 - twisted.internet.test.test_sigchld no longer incorrectly fails when
   run after certain other tests. (#6161)
 - twisted.internet.test.test_gireactor no longer fails when using
   pygobject 3.4 and gtk 3.6 when X11 is unavailable. (#6170)
 - twisted/python/sendmsg.c no longer fails to build on OpenBSD.
   (#5907)

Improved Documentation
----------------------
 - The endpoint howto now lists TCP IPv6 server endpoint in the list
   of endpoints included with Twisted. (#5741)

Deprecations and Removals
-------------------------
 - The minimum required version of zope.interface is now 3.6.0.
   (#5683)
 - twisted.internet.interfaces.IReactorArbitrary and
   twisted.application.internet.GenericServer and GenericClient,
   deprecated since Twisted 10.1, have been removed. (#5943)
 - twisted.internet.interfaces.IFinishableConsumer, deprecated since
   Twisted 11.1, has been removed. (#5944)
 - twisted.python.failure has removed all support for string
   exceptions. (#5948)
 - assertTrue, assertEqual, and the other free-functions in
   twisted.trial.unittest for writing assertions, deprecated since
   prior to Twisted 2.3, have been removed. (#5963)
 - Ports, connectors, wakers and other reactor-related types no longer
   log a nice warning when they are erroneously pickled. Pickling of
   such objects continues to be unsupported. (#5979)
 - twisted.python.components.Componentized no longer inherits from
   Versioned. (#5983)
 - twisted.protocols.basic.NetstringReceiver.sendString no longer
   accepts objects other than bytes; the removed behavior was
   deprecated in Twisted 10.0. (#6025)
 - The lookupRecord method of twisted.internet.interfaces.IResolver,
   never implemented or called by Twisted, has been removed. (#6091)

Other
-----
 - #4286, #4920, #5627, #5785, #5860, #5865, #5873, #5874, #5877,
   #5879, #5884, #5885, #5886, #5891, #5896, #5897, #5899, #5900,
   #5901, #5903, #5906, #5908, #5912, #5913, #5914, #5916, #5917,
   #5931, #5932, #5933, #5934, #5935, #5939, #5942, #5947, #5956,
   #5959, #5967, #5969, #5970, #5972, #5973, #5974, #5975, #5980,
   #5985, #5986, #5990, #5995, #6002, #6003, #6005, #6007, #6009,
   #6010, #6018, #6019, #6022, #6023, #6033, #6036, #6039, #6041,
   #6043, #6052, #6053, #6054, #6055, #6060, #6061, #6065, #6067,
   #6068, #6069, #6084, #6087, #6088, #6097, #6099, #6100, #6103,
   #6109, #6114, #6139, #6140, #6141, #6142, #6157, #6158, #6159,
   #6163, #6172, #6182, #6190, #6194, #6204, #6209


Twisted Conch 12.3.0 (2012-12-20)
=================================

Bugfixes
--------
 - Passing multiple --auth arguments to conch now correctly adds all
   the specified checkers to the conch server (#5881)
 - ckeygen --showpub now uses OPENSSH as default display, instead of
   breaking because no display type was passed. (#5889)
 - ckeygen --showpub catches EncryptedKeyError instead of BadKeyError
   to detect that a key needs to be decrypted with a passphrase.
   (#5890)

Other
-----
 - #5923


Twisted Lore 12.3.0 (2012-12-20)
================================

No significant changes have been made for this release.


Twisted Mail 12.3.0 (2012-12-20)
================================

Bugfixes
--------
 - twisted.mail.imap4._FetchParser now raises
   IllegalClientResponse("Invalid Argument") when protocol encounters
   extra bytes at the end of a valid FETCH command. (#4000)

Improved Documentation
----------------------
 - twisted.mail.tap now documents example usage in its longdesc
   output for the 'mail' plugin (#5922)

Other
-----
 - #3751


Twisted Names 12.3.0 (2012-12-20)
=================================

Deprecations and Removals
-------------------------
 - The `protocol` attribute of twisted.names.client.Resolver,
   deprecated since Twisted 8.2, has been removed. (#6045)
 - twisted.names.hosts.Resolver is no longer a
   `twisted.persisted.styles.Versioned` subclass. (#6092)

Other
-----
 - #5594, #6056, #6057, #6058, #6059, #6093


Twisted News 12.3.0 (2012-12-20)
================================

No significant changes have been made for this release.


Twisted Pair 12.3.0 (2012-12-20)
================================

No significant changes have been made for this release.


Twisted Runner 12.3.0 (2012-12-20)
==================================

No significant changes have been made for this release.


Twisted Web 12.3.0 (2012-12-20)
===============================

Features
--------
 - twisted.web.server.Site now supports an encoders argument to encode
   request content, twisted.web.server.GzipEncoderFactory being the
   first one provided. (#104)

Bugfixes
--------
 - twisted.web.http.HTTPChannel.headerReceived now catches the error
   if the Content-Length header is not an integer and return a 400 Bad
   Request response. (#6029)
 - twisted.web.http.HTTPChannel now drops the connection and issues a
   400 error upon receipt of a chunk-encoding encoded request with a
   bad chunk-length field. (#6030)

Improved Documentation
----------------------
 - twisted.web.iweb.IRequest now documents its `content` attribute and
   a new "web in 60 seconds" howto demonstrates its use. (#6181)

Other
-----
 - #5882, #5883, #5887, #5920, #6031, #6077, #6078, #6079, #6080,
   #6110, #6113, #6196, #6205


Twisted Words 12.3.0 (2012-12-20)
=================================

Improved Documentation
----------------------
 - The Twisted Words code examples now documents inside each example
   description on how to run it. (#5589)


Twisted Core 12.2.0 (2012-08-26)
================================

Starting with the release after 12.2, Twisted will begin requiring
zope.interface 3.6 (as part of Python 3 support).

This is the last Twisted release supporting Python 2.6 on Windows.

Features
--------
 - twisted.protocols.sip.MessageParser now handles multiline headers.
   (#2198)
 - twisted.internet.endpoints now provides StandardIOEndpoint, a
   Standard I/O endpoint. (#4697)
 - If a FTPCmdError occurs during twisted.protocols.ftp.FTP.ftp_RETR
   sending the file (i.e. it is raised by the IReadFile.send method it
   invokes), then it will use that to return an error to the client
   rather than necessarily sending a 426 CNX_CLOSED_TXFR_ABORTED
   error. (#4913)
 - twisted.internet.interfaces.IReactorSocket.adoptStreamConnection is
   implemented by some reactors as a way to add an existing
   established connection to them. (#5570)
 - twisted.internet.endpoints now provides TCP6ServerEndpoint, an IPv6
   TCP server endpoint. (#5694)
 - twisted.internet.endpoints now provides TCP6ClientEndpoint, an IPv6
   TCP client endpoint. (#5695)
 - twisted.internet.endpoints.serverFromString, the endpoint string
   description feature, can now be used to create IPv6 TCP servers.
   (#5699)
 - twisted.internet.endpoints.serverFromString, the endpoint string
   description feature, can now be used to create servers that run on
   Standard I/O. (#5729)
 - twisted.trial.unittest now offers SynchronousTestCase, a test case
   base class that provides usability improvements but not reactor-
   based testing features. (#5853)

Bugfixes
--------
 - twisted.internet.Process.signalProcess now catches ESRCH raised by
   os.kill call and raises ProcessExitedAlready instead. (#2420)
 - TLSMemoryBIOProtocol (and therefore all SSL transports if pyOpenSSL
   >= 0.10) now provides the interfaces already provided by the
   underlying transport. (#5182)

Deprecations and Removals
-------------------------
 - Python 2.5 is no longer supported. (#5553)
 - The --extra option of trial, deprecated since 11.0, is removed now.
   (#3374)
 - addPluginDir and getPluginDirs in twisted.python.util are
   deprecated now. (#4533)
 - twisted.trial.runner.DocTestCase, deprecated in Twisted 8.0, has
   been removed. (#5554)
 - startKeepingErrors, flushErrors, ignoreErrors, and clearIgnores in
   twisted.python.log (deprecated since Twisted 2.5) are removed now.
   (#5765)
 - unzip, unzipIter, and countZipFileEntries in
   twisted.python.zipstream (deprecated in Twisted 11.0) are removed
   now. (#5766)
 - twisted.test.time_helpers, deprecated since Twisted 10.0, has been
   removed. (#5820)

Other
-----
 - #4244, #4532, #4930, #4999, #5129, #5138, #5385, #5521, #5655,
   #5674, #5679, #5687, #5688, #5689, #5692, #5707, #5734, #5736,
   #5745, #5746, #5747, #5749, #5784, #5816, #5817, #5818, #5819,
   #5830, #5857, #5858, #5859, #5869, #5632


Twisted Conch 12.2.0 (2012-08-26)
=================================

Features
--------
 - twisted.conch.ssh.transport.SSHTransport now returns an
   SSHTransportAddress from the getPeer() and getHost() methods.
   (#2997)

Bugfixes
--------
 - twisted.conch now supports commercial SSH implementations which
   don't comply with the IETF standard (#1902)
 - twisted.conch.ssh.userauth now works correctly with hash
   randomization enabled. (#5776)
 - twisted.conch no longer relies on __builtins__ being a dict, which
   is a purely CPython implementation detail (#5779)

Other
-----
 - #5496, #5617, #5700, #5748, #5777


Twisted Lore 12.2.0 (2012-08-26)
================================

No significant changes have been made for this release.


Twisted Mail 12.2.0 (2012-08-26)
================================

Bugfixes
--------
 - twisted.mail.imap4.IMAP4Server will now generate an error response
   when it receives an illegal SEARCH term from a client. (#4080)
 - twisted.mail.imap4 now serves BODYSTRUCTURE responses which provide
   more information and conform to the IMAP4 RFC more closely. (#5763)

Deprecations and Removals
-------------------------
 - twisted.mail.protocols.SSLContextFactory is now deprecated. (#4963)
 - The --passwordfile option to twistd mail is now removed. (#5541)

Other
-----
 - #5697, #5750, #5751, #5783


Twisted Names 12.2.0 (2012-08-26)
=================================

Features
--------
 - twisted.names.srvconnect.SRVConnector now takes a default port to
   use when SRV lookup fails. (#3456)

Other
-----
 - #5647


Twisted News 12.2.0 (2012-08-26)
================================

No significant changes have been made for this release.


Twisted Pair 12.2.0 (2012-08-26)
================================

No significant changes have been made for this release.


Twisted Runner 12.2.0 (2012-08-26)
==================================

No significant changes have been made for this release.


Twisted Web 12.2.0 (2012-08-26)
===============================

Deprecations and Removals
-------------------------
 - twisted.web.static.FileTransfer, deprecated since 9.0, is removed
   now. Use a subclass of StaticProducer instead. (#5651)
 - ErrorPage, NoResource and ForbiddenResource in twisted.web.error
   were deprecated since 9.0 and are removed now. (#5659)
 - twisted.web.google, deprecated since Twisted 11.1, is removed now.
   (#5768)

Other
-----
 - #5665


Twisted Words 12.2.0 (2012-08-26)
=================================

No significant changes have been made for this release.

Other
-----
 - #5752, #5753


Twisted Core 12.1.0 (2012-06-02)
================================

Features
--------
 - The kqueue reactor has been revived. (#1918)
 - twisted.python.filepath now provides IFilePath, an interface for
   file path objects. (#2176)
 - New gtk3 and gobject-introspection reactors have been added.
   (#4558)
 - gtk and glib reactors now run I/O and scheduled events with lower
   priority, to ensure the UI stays responsive. (#5067)
 - IReactorTCP.connectTCP() can now accept IPv6 address literals
   (although not hostnames) in order to support connecting to IPv6
   hosts. (#5085)
 - twisted.internet.interfaces.IReactorSocket, a new interface, is now
   supported by some reactors to listen on sockets set up by external
   software (eg systemd or launchd). (#5248)
 - twisted.internet.endpoints.clientFromString now also supports
   strings in the form of tcp:example.com:80 and ssl:example.com:4321
   (#5358)
 - twisted.python.constants.Flags now provides a way to define
   collections of flags for bitvector-type uses. (#5384)
 - The epoll(7)-based reactor is now the default reactor on Linux.
   (#5478)
 - twisted.python.runtime.platform.isLinux can be used to check if
   Twisted is running on Linux. (#5491)
 - twisted.internet.endpoints.serverFromString now recognizes a
   "systemd" endpoint type, for listening on a server port inherited
   from systemd. (#5575)
 - Connections created using twisted.internet.interfaces.IReactorUNIX
   now support sending and receiving file descriptors between
   different processes. (#5615)
 - twisted.internet.endpoints.clientFromString now supports UNIX
   client endpoint strings with the path argument specified like
   "unix:/foo/bar" in addition to the old style, "unix:path=/foo/bar".
   (#5640)
 - twisted.protocols.amp.Descriptor is a new AMP argument type which
   supports passing file descriptors as AMP command arguments over
   UNIX connections. (#5650)

Bugfixes
--------
 - twisted.internet.abstract.FileDescriptor implements
   twisted.internet.interfaces.IPushProducer instead of
   twisted.internet.interfaces.IProducer.
   twisted.internet.iocpreactor.abstract.FileHandle implements
   twisted.internet.interfaces.IPushProducer instead of
   twisted.internet.interfaces.IProducer. (#4386)
 - The epoll reactor now supports reading/writing to regular files on
   stdin/stdout. (#4429)
 - Calling .cancel() on any Twisted-provided client endpoint
   (TCP4ClientEndpoint, UNIXClientEndpoint, SSL4ClientEndpoint) now
   works as documented, rather than logging an AlreadyCalledError.
   (#4710)
 - A leak of OVERLAPPED structures in some IOCP error cases has been
   fixed. (#5372)
 - twisted.internet._pollingfile._PollableWritePipe now checks for
   outgoing unicode data in write() and writeSequence() instead of
   checkWork(). (#5412)

Improved Documentation
----------------------
 - "Working from Twisted's Subversion repository" links to UQDS and
   Combinator are now updated. (#5545)
 - Added tkinterdemo.py, an example of Tkinter integration. (#5631)

Deprecations and Removals
-------------------------
 - The 'unsigned' flag to twisted.scripts.tap2rpm.MyOptions is now
   deprecated.  (#4086)
 - Removed the unreachable _fileUrandom method from
   twisted.python.randbytes.RandomFactory. (#4530)
 - twisted.persisted.journal is removed, deprecated since Twisted
   11.0. (#4805)
 - Support for pyOpenSSL 0.9 and older is now deprecated.  pyOpenSSL
   0.10 or newer will soon be required in order to use Twisted's SSL
   features. (#4974)
 - backwardsCompatImplements and fixClassImplements are removed from
   twisted.python.components, deprecated in 2006. (#5034)
 - twisted.python.reflect.macro was removed, deprecated since Twisted
   8.2. (#5035)
 - twisted.python.text.docstringLStrip, deprecated since Twisted
   10.2.0, has been removed (#5036)
 - Removed the deprecated dispatch and dispatchWithCallback methods
   from twisted.python.threadpool.ThreadPool (deprecated since 8.0)
   (#5037)
 - twisted.scripts.tapconvert is now deprecated. (#5038)
 - twisted.python.reflect's Settable, AccessorType, PropertyAccessor,
   Accessor, OriginalAccessor and Summer are now deprecated.  (#5451)
 - twisted.python.threadpool.ThreadSafeList (deprecated in 10.1) is
   removed. (#5473)
 - twisted.application.app.initialLog, deprecated since Twisted 8.2.0,
   has been removed. (#5480)
 - twisted.spread.refpath was deleted, deprecated since Twisted 9.0.
   (#5482)
 - twisted.python.otp, deprecated since 9.0, is removed. (#5493)
 - Removed `dsu`, `moduleMovedForSplit`, and `dict` from
   twisted.python.util (deprecated since 10.2) (#5516)

Other
-----
 - #2723, #3114, #3398, #4388, #4489, #5055, #5116, #5242, #5380,
   #5392, #5447, #5457, #5484, #5489, #5492, #5494, #5512, #5523,
   #5558, #5572, #5583, #5593, #5620, #5621, #5623, #5625, #5637,
   #5652, #5653, #5656, #5657, #5660, #5673


Twisted Conch 12.1.0 (2012-06-02)
=================================

Features
--------
 - twisted.conch.tap now supports cred plugins (#4753)

Bugfixes
--------
 - twisted.conch.client.knownhosts now handles errors encountered
   parsing hashed entries in a known hosts file. (#5616)

Improved Documentation
----------------------
 - Conch examples window.tac and telnet_echo.tac now have better
   explanations. (#5590)

Other
-----
 - #5580


Twisted Lore 12.1.0 (2012-06-02)
================================

Bugfixes
--------
 - twisted.plugins.twisted_lore's MathProcessor plugin is now
   associated with the correct implementation module. (#5326)


Twisted Mail 12.1.0 (2012-06-02)
================================

Bugfixes
--------
 - twistd mail --auth, broken in 11.0, now correctly connects
   authentication to the portal being used (#5219)

Other
-----
 - #5686


Twisted Names 12.1.0 (2012-06-02)
=================================

Features
--------
 - "twistd dns" secondary server functionality and
   twisted.names.secondary now support retrieving zone information
   from a master running on a non-standard DNS port. (#5468)

Bugfixes
--------
 - twisted.names.dns.DNSProtocol instances no longer throw an
   exception when disconnecting. (#5471)
 - twisted.names.tap.makeService (thus also "twistd dns") now makes a
   DNS server which gives precedence to the hosts file from its
   configuration over the remote DNS servers from its configuration.
   (#5524)
 - twisted.name.cache.CacheResolver now makes sure TTLs on returned
   results are never negative. (#5579)
 - twisted.names.cache.CacheResolver entries added via the initializer
   are now timed out correctly. (#5638)

Improved Documentation
----------------------
 - The examples now contain instructions on how to run them and
   descriptions in the examples index. (#5588)

Deprecations and Removals
-------------------------
 - The deprecated twisted.names.dns.Record_mx.exchange attribute was
   removed. (#4549)


Twisted News 12.1.0 (2012-06-02)
================================

Bugfixes
--------
 - twisted.news.nntp.NNTPServer now has additional test coverage and
   less redundant implementation code. (#5537)

Deprecations and Removals
-------------------------
 - The ability to pass a string article to NNTPServer._gotBody and
   NNTPServer._gotArticle in t.news.nntp has been deprecated for years
   and is now removed. (#4548)


Twisted Pair 12.1.0 (2012-06-02)
================================

No significant changes have been made for this release.


Twisted Runner 12.1.0 (2012-06-02)
==================================

Deprecations and Removals
-------------------------
 - ProcessMonitor.active, consistencyDelay, and consistency in
   twisted.runner.procmon were deprecated since 10.1 have been
   removed. (#5517)


Twisted Web 12.1.0 (2012-06-02)
===============================

Features
--------
 - twisted.web.client.Agent and ProxyAgent now support persistent
   connections. (#3420)
 - Added twisted.web.template.renderElement, a function which renders
   an Element to a response. (#5395)
 - twisted.web.client.HTTPConnectionPool now ensures that failed
   queries on persistent connections are retried, when possible.
   (#5479)
 - twisted.web.template.XMLFile now supports FilePath objects. (#5509)
 - twisted.web.template.renderElement takes a doctype keyword
   argument, which will be written as the first line of the response,
   defaulting to the HTML5 doctype. (#5560)

Bugfixes
--------
 - twisted.web.util.formatFailure now quotes all data in its output to
   avoid it being mistakenly interpreted as markup. (#4896)
 - twisted.web.distrib now lets distributed servers set the response
   message. (#5525)

Deprecations and Removals
-------------------------
 - PHP3Script and PHPScript were removed from twisted.web.twcgi,
   deprecated since 10.1. Use twcgi.FilteredScript instead. (#5456)
 - twisted.web.template.XMLFile's support for file objects and
   filenames is now deprecated.  Use the new support for FilePath
   objects. (#5509)
 - twisted.web.server.date_time_string and
   twisted.web.server.string_date_time are now deprecated in favor of
   twisted.web.http.datetimeToString and twisted.web.
   http.stringToDatetime (#5535)

Other
-----
 - #4966, #5460, #5490, #5591, #5602, #5609, #5612


Twisted Words 12.1.0 (2012-06-02)
=================================

Bugfixes
--------
 - twisted.words.protocols.irc.DccChatFactory.buildProtocol now
   returns the protocol object that it creates (#3179)
 - twisted.words.im no longer offers an empty threat of a rewrite on
   import. (#5598)

Other
-----
 - #5555, #5595


Twisted Core 12.0.0 (2012-02-10)
================================

Features
--------
 - The interface argument to IReactorTCP.listenTCP may now be an IPv6
   address literal, allowing the creation of IPv6 TCP servers. (#5084)
 - twisted.python.constants.Names now provides a way to define
   collections of named constants, similar to the "enum type" feature
   of C or Java. (#5382)
 - twisted.python.constants.Values now provides a way to define
   collections of named constants with arbitrary values. (#5383)

Bugfixes
--------
 - Fixed an obscure case where connectionLost wasn't called on the
   protocol when using half-close. (#3037)
 - UDP ports handle socket errors better on Windows. (#3396)
 - When idle, the gtk2 and glib2 reactors no longer wake up 10 times a
   second. (#4376)
 - Prevent a rare situation involving TLS transports, where a producer
   may be erroneously left unpaused. (#5347)
 - twisted.internet.iocpreactor.iocpsupport now has fewer 64-bit
   compile warnings. (#5373)
 - The GTK2 reactor is now more responsive on Windows. (#5396)
 - TLS transports now correctly handle producer registration after the
   connection has been lost. (#5439)
 - twisted.protocols.htb.Bucket now empties properly with a non-zero
   drip rate. (#5448)
 - IReactorSSL and ITCPTransport.startTLS now synchronously propagate
   errors from the getContext method of context factories, instead of
   being capturing them and logging them as unhandled. (#5449)

Improved Documentation
----------------------
 - The multicast documentation has been expanded. (#4262)
 - twisted.internet.defer.Deferred now documents more return values.
   (#5399)
 - Show a better starting page at
   http://twistedmatrix.com/documents/current (#5429)

Deprecations and Removals
-------------------------
 - Remove the deprecated module twisted.enterprise.reflector. (#4108)
 - Removed the deprecated module twisted.enterprise.row. (#4109)
 - Remove the deprecated module twisted.enterprise.sqlreflector.
   (#4110)
 - Removed the deprecated module twisted.enterprise.util, as well as
   twisted.enterprise.adbapi.safe. (#4111)
 - Python 2.4 is no longer supported on any platform. (#5060)
 - Removed printTraceback and noOperation from twisted.spread.pb,
   deprecated since Twisted 8.2. (#5370)

Other
-----
 - #1712, #2725, #5284, #5325, #5331, #5362, #5364, #5371, #5407,
   #5427, #5430, #5431, #5440, #5441


Twisted Conch 12.0.0 (2012-02-10)
=================================

Features
--------
 - use Python shadow module for authentication if it's available
   (#3242)

Bugfixes
--------
 - twisted.conch.ssh.transport.messages no longer ends with with old
   message IDs on platforms with differing dict() orderings (#5352)

Other
-----
 - #5225


Twisted Lore 12.0.0 (2012-02-10)
================================

No significant changes have been made for this release.


Twisted Mail 12.0.0 (2012-02-10)
================================

No significant changes have been made for this release.


Twisted Names 12.0.0 (2012-02-10)
=================================

Bugfixes
--------
 - twisted.names.dns.Message now sets the `auth` flag on RRHeader
   instances it creates to reflect the authority of the message
   itself. (#5421)


Twisted News 12.0.0 (2012-02-10)
================================

No significant changes have been made for this release.


Twisted Pair 12.0.0 (2012-02-10)
================================

No significant changes have been made for this release.


Twisted Runner 12.0.0 (2012-02-10)
==================================

No significant changes have been made for this release.


Twisted Web 12.0.0 (2012-02-10)
===============================

Features
--------
 - twisted.web.util.redirectTo now raises TypeError if the URL passed
   to it is a unicode string instead of a byte string. (#5236)
 - The new class twisted.web.template.CharRef provides support for
   inserting numeric character references in output generated by
   twisted.web.template. (#5408)

Improved Documentation
----------------------
 - The Twisted Web howto now has a section on proxies and reverse
   proxies. (#399)
 - The web client howto now covers ContentDecoderAgent and links to an
   example of its use. (#5415)

Other
-----
 - #5404, #5438


Twisted Words 12.0.0 (2012-02-10)
=================================

Improved Documentation
----------------------
 - twisted.words.im.basechat now has improved API documentation.
   (#2458)

Other
-----
 - #5401


Twisted Core 11.1.0 (2011-11-15)
================================

Features
--------
 - TCP and TLS transports now support abortConnection() which, unlike
   loseConnection(), always closes the connection immediately. (#78)
 - Failures received over PB when tracebacks are disabled now display
   the wrapped exception value when they are printed. (#581)
 - twistd now has a --logger option, allowing the use of custom log
   observers. (#638)
 - The default reactor is now poll(2) on platforms that support it.
   (#2234)
 - twisted.internet.defer.inlineCallbacks(f) now raises TypeError when
   f returns something other than a generator or uses returnValue as a
   non-generator. (#2501)
 - twisted.python.usage.Options now supports performing Zsh tab-
   completion on demand. Tab-completion for Twisted commands is
   supported out-of-the-box on any recent zsh release. Third-party
   commands may take advantage of zsh completion by copying the
   provided stub file. (#3078)
 - twisted.protocols.portforward now uses flow control between its
   client and server connections to avoid having to buffer an
   unbounded amount of data when one connection is slower than the
   other. (#3350)
 - On Windows, the select, IOCP, and Gtk2 reactors now implement
   IReactorWin32Events (most notably adding support for serial ports
   to these reactors). (#4862)
 - twisted.python.failure.Failure no longer captures the state of
   locals and globals of all stack frames by default, because it is
   expensive to do and rarely used.  You can pass captureVars=True to
   Failure's constructor if you want to capture this data. (#5011)
 - twisted.web.client now supports automatic content-decoding via
   twisted.web.client.ContentDecoderAgent, gzip being supported for
   now. (#5053)
 - Protocols may now implement ILoggingContext to customize their
   logging prefix.  twisted.protocols.policies.ProtocolWrapper and the
   endpoints wrapper now take advantage of this feature to ensure the
   application protocol is still reflected in logs. (#5062)
 - AMP's raw message-parsing performance was increased by
   approximately 12%. (#5075)
 - Twisted is now installable on PyPy, because some incompatible C
   extensions are no longer built. (#5158)
 - twisted.internet.defer.gatherResults now accepts a consumeErrors
   parameter, with the same meaning as the corresponding argument for
   DeferredList. (#5159)
 - Added RMD (remove directory) support to the FTP client. (#5259)
 - Server factories may now implement ILoggingContext to customize the
   name that is logged when the reactor uses one to start listening on
   a port. (#5292)
 - The implementations of ITransport.writeSequence will now raise
   TypeError if passed unicode strings. (#3896)
 - iocp reactor now operates correctly on 64 bit Python runtimes.
   (#4669)
 - twistd ftp now supports the cred plugin. (#4752)
 - twisted.python.filepath.FilePath now has an API to retrieve the
   permissions of the underlying file, and two methods to determine
   whether it is a block device or a socket.  (#4813)
 - twisted.trial.unittest.TestCase is now compatible with Python 2.7's
   assertDictEqual method. (#5291)

Bugfixes
--------
 - The IOCP reactor now does not try to erroneously pause non-
   streaming producers. (#745)
 - Unicode print statements no longer blow up when using Twisted's
   logging system. (#1990)
 - Process transports on Windows now support the `writeToChild` method
   (but only for stdin). (#2838)
 - Zsh tab-completion of Twisted commands no longer relies on
   statically generated files, but instead generates results on-the-
   fly - ensuring accurate tab-completion for the version of Twisted
   actually in use. (#3078)
 - LogPublishers don't use the global log publisher for reporting
   broken observers anymore. (#3307)
 - trial and twistd now add the current directory to sys.path even
   when running as root or on Windows. mktap, tapconvert, and
   pyhtmlizer no longer add the current directory to sys.path. (#3526)
 - twisted.internet.win32eventreactor now stops immediately if
   reactor.stop() is called from an IWriteDescriptor.doWrite
   implementation instead of delaying shutdown for an arbitrary period
   of time. (#3824)
 - twisted.python.log now handles RuntimeErrors more gracefully, and
   always restores log observers after an exception is raised. (#4379)
 - twisted.spread now supports updating new-style RemoteCache
   instances. (#4447)
 - twisted.spread.pb.CopiedFailure will no longer be thrown into a
   generator as a (deprecated) string exception but as a
   twisted.spread.pb.RemoteException. (#4520)
 - trial now gracefully handles the presence of objects in sys.modules
   which respond to attributes being set on them by modifying
   sys.modules. (#4748)
 - twisted.python.deprecate.deprecatedModuleAttribute no longer
   spuriously warns twice when used to deprecate a module within a
   package.  This should make it easier to write unit tests for
   deprecated modules. (#4806)
 - When pyOpenSSL 0.10 or newer is available, SSL support now uses
   Twisted for all I/O and only relies on OpenSSL for cryptography,
   avoiding a number of tricky, potentially broken edge cases. (#4854)
 - IStreamClientEndpointStringParser.parseStreamClient now correctly
   describes how it will be called by clientFromString (#4956)
 - twisted.internet.defer.Deferreds are 10 times faster at handling
   exceptions raised from callbacks, except when setDebugging(True)
   has been called. (#5011)
 - twisted.python.filepath.FilePath.copyTo now raises OSError(ENOENT)
   if the source path being copied does not exist. (#5017)
 - twisted.python.modules now supports iterating over namespace
   packages without yielding duplicates. (#5030)
 - reactor.spawnProcess now uses the resource module to guess the
   maximum possible open file descriptor when /dev/fd exists but gives
   incorrect results. (#5052)
 - The memory BIO TLS/SSL implementation now supports producers
   correctly. (#5063)
 - twisted.spread.pb.Broker no longer creates an uncollectable
   reference cycle when the logout callback holds a reference to the
   client mind object. (#5079)
 - twisted.protocols.tls, and SSL/TLS support in general, now do clean
   TLS close alerts when disconnecting. (#5118)
 - twisted.persisted.styles no longer uses the deprecated allYourBase
   function (#5193)
 - Stream client endpoints now start (doStart) and stop (doStop) the
   factory passed to the connect method, instead of a different
   implementation-detail factory. (#5278)
 - SSL ports now consistently report themselves as SSL rather than TCP
   when logging their close message. (#5292)
 - Serial ports now deliver connectionLost to the protocol when
   closed. (#3690)
 - win32eventreactor now behaves better in certain rare cases in which
   it previously would have failed to deliver connection lost
   notification to a protocol. (#5233)

Improved Documentation
----------------------
 - Test driven development with Twisted and Trial is now documented in
   a how-to. (#2443)
 - A new howto-style document covering twisted.protocols.amp has been
   added. (#3476)
 - Added sample implementation of a Twisted push producer/consumer
   system. (#3835)
 - The "Deferred in Depth" tutorial now includes accurate output for
   the deferred_ex2.py example. (#3941)
 - The server howto now covers the Factory.buildProtocol method.
   (#4761)
 - The testing standard and the trial tutorial now recommend the
   `assertEqual` form of assertions rather than the `assertEquals` to
   coincide with the standard library unittest's preference. (#4989)
 - twisted.python.filepath.FilePath's methods now have more complete
   API documentation (docstrings). (#5027)
 - The Clients howto now uses buildProtocol more explicitly, hopefully
   making it easier to understand where Protocol instances come from.
   (#5044)

Deprecations and Removals
-------------------------
 - twisted.internet.interfaces.IFinishableConsumer is now deprecated.
   (#2661)
 - twisted.python.zshcomp is now deprecated in favor of the tab-
   completion system in twisted.python.usage (#3078)
 - The unzip and unzipIter functions in twisted.python.zipstream are
   now deprecated. (#3666)
 - Options.optStrings, deprecated for 7 years, has been removed.  Use
   Options.optParameters instead. (#4552)
 - Removed the deprecated twisted.python.dispatch module. (#5023)
 - Removed the twisted.runner.procutils module that was deprecated in
   Twisted 2.3. (#5049)
 - Removed twisted.trial.runner.DocTestSuite, deprecated in Twisted
   8.0. (#5111)
 - twisted.scripts.tkunzip is now deprecated. (#5140)
 - Deprecated option --password-file in twistd ftp (#4752)
 - mktap, deprecated since Twisted 8.0, has been removed. (#5293)

Other
-----
 - #1946, #2562, #2674, #3074, #3077, #3776, #4227, #4539, #4587,
   #4619, #4624, #4629, #4683, #4690, #4702, #4778, #4944, #4945,
   #4949, #4952, #4957, #4979, #4980, #4987, #4990, #4994, #4995,
   #4997, #5003, #5008, #5009, #5012, #5019, #5042, #5046, #5051,
   #5065, #5083, #5088, #5089, #5090, #5101, #5108, #5109, #5112,
   #5114, #5125, #5128, #5131, #5136, #5139, #5144, #5146, #5147,
   #5156, #5160, #5165, #5191, #5205, #5215, #5217, #5218, #5223,
   #5243, #5244, #5250, #5254, #5261, #5266, #5273, #5299, #5301,
   #5302, #5304, #5308, #5311, #5321, #5322, #5327, #5328, #5332,
   #5336


Twisted Conch 11.1.0 (2011-11-15)
=================================

Features
--------
 - twisted.conch.ssh.filetransfer.FileTransferClient now handles short
   status messages, not strictly allowed by the RFC, but sent by some
   SSH implementations. (#3009)
 - twisted.conch.manhole now supports CTRL-A and CTRL-E to trigger
   HOME and END functions respectively. (#5252)

Bugfixes
--------
 - When run from an unpacked source tarball or a VCS checkout, the
   bin/conch/ scripts will now use the version of Twisted they are
   part of. (#3526)
 - twisted.conch.insults.window.ScrolledArea now passes no extra
   arguments to object.__init__ (which works on more versions of
   Python). (#4197)
 - twisted.conch.telnet.ITelnetProtocol now has the correct signature
   for its unhandledSubnegotiation() method. (#4751)
 - twisted.conch.ssh.userauth.SSHUserAuthClient now more closely
   follows the RFC 4251 definition of boolean values when negotiating
   for key-based authentication, allowing better interoperability with
   other SSH implementations. (#5241)
 - twisted.conch.recvline.RecvLine now ignores certain function keys
   in its keystrokeReceived method instead of raising an exception.
   (#5246)

Deprecations and Removals
-------------------------
 - The --user option to `twistd manhole' has been removed as it was
   dead code with no functionality associated with it. (#5283)

Other
-----
 - #5107, #5256, #5349


Twisted Lore 11.1.0 (2011-11-15)
================================

Bugfixes
--------
 - When run from an unpacked source tarball or a VCS checkout,
   bin/lore/lore will now use the version of Twisted it is part of.
   (#3526)

Deprecations and Removals
-------------------------
 - Removed compareMarkPos and comparePosition from lore.tree,
   deprecated in Twisted 9.0. (#5127)


Twisted Mail 11.1.0 (2011-11-15)
================================

Features
--------
 - twisted.mail.smtp.LOGINCredentials now generates challenges with
   ":" instead of "\0" for interoperability with Microsoft Outlook.
   (#4692)

Bugfixes
--------
 - When run from an unpacked source tarball or a VCS checkout,
   bin/mail/mailmail will now use the version of Twisted it is part
   of. (#3526)

Other
-----
 - #4796, #5006


Twisted Names 11.1.0 (2011-11-15)
=================================

Features
--------
 - twisted.names.dns.Message now parses records of unknown type into
   instances of a new `UnknownType` class. (#4603)

Bugfixes
--------
 - twisted.names.dns.Name now detects loops in names it is decoding
   and raises an exception.  Previously it would follow the loop
   forever, allowing a remote denial of service attack against any
   twisted.names client or server. (#5064)
 - twisted.names.hosts.Resolver now supports IPv6 addresses; its
   lookupAddress method now filters them out and its lookupIPV6Address
   method is now implemented. (#5098)


Twisted News 11.1.0 (2011-11-15)
================================

No significant changes have been made for this release.


Twisted Pair 11.1.0 (2011-11-15)
================================

No significant changes have been made for this release.


Twisted Runner 11.1.0 (2011-11-15)
==================================

No significant changes have been made for this release.


Twisted Web 11.1.0 (2011-11-15)
===============================

Features
--------
 - twisted.web.client.ProxyAgent is a new HTTP/1.1 web client which
   adds proxy support. (#1774)
 - twisted.web.client.Agent now takes optional connectTimeout and
   bindAddress arguments which are forwarded to the subsequent
   connectTCP/connectSSL call. (#3450)
 - The new class twisted.web.client.FileBodyProducer makes it easy to
   upload data in HTTP requests made using the Agent client APIs.
   (#4017)
 - twisted.web.xmlrpc.XMLRPC now allows its lookupProcedure method to
   be overridden to change how XML-RPC procedures are dispatched.
   (#4836)
 - A new HTTP cookie-aware Twisted Web Agent wrapper is included in
   twisted.web.client.CookieAgent (#4922)
 - New class twisted.web.template.TagLoader provides an
   ITemplateLoader implementation which loads already-created
   twisted.web.iweb.IRenderable providers. (#5040)
 - The new class twisted.web.client.RedirectAgent adds redirect
   support to the HTTP 1.1 client stack. (#5157)
 - twisted.web.template now supports HTML tags from the HTML5
   standard, including <canvas> and <video>. (#5306)

Bugfixes
--------
 - twisted.web.client.getPage and .downloadPage now only fire their
   result Deferred after the underlying connection they use has been
   closed. (#3796)
 - twisted.web.server now omits the default Content-Type header from
   NOT MODIFIED responses. (#4156)
 - twisted.web.server now responds correctly to 'Expect: 100-continue'
   headers, although this is not yet usefully exposed to user code.
   (#4673)
 - twisted.web.client.Agent no longer raises an exception if a server
   responds and closes the connection before the request has been
   fully transmitted. (#5013)
 - twisted.web.http_headers.Headers now correctly capitalizes the
   header names Content-MD5, DNT, ETag, P3P, TE, and X-XSS-Protection.
   (#5054)
 - twisted.web.template now escapes more inputs to comments which
   require escaping in the output. (#5275)

Improved Documentation
----------------------
 - The twisted.web.template howto now documents the common idiom of
   yielding tag clones from a renderer. (#5286)
 - CookieAgent is now documented in the twisted.web.client how-to.
   (#5110)

Deprecations and Removals
-------------------------
 - twisted.web.google is now deprecated. (#5209)

Other
-----
 - #4951, #5057, #5175, #5288, #5316


Twisted Words 11.1.0 (2011-11-15)
=================================

Features
--------
 - twisted.words.protocols.irc.IRCClient now uses a PING heartbeat as
   a keepalive to avoid losing an IRC connection without being aware
   of it. (#5047)

Bugfixes
--------
 - twisted.words.protocols.irc.IRCClient now replies only once to
   known CTCP queries per message and not at all to unknown CTCP
   queries. (#5029)
 - IRCClient.msg now determines a safe maximum command length,
   drastically reducing the chance of relayed text being truncated on
   the server side. (#5176)

Deprecations and Removals
-------------------------
 - twisted.words.protocols.irc.IRCClient.me was deprecated in Twisted
   9.0 and has been removed. Use IRCClient.describe instead. (#5059)

Other
-----
 - #5025, #5330


Twisted Core 11.0.0 (2011-04-01)
================================

Features
--------
 - The reactor is not restartable, but it would previously fail to
   complain. Now, when you restart an unrestartable reactor, you get
   an exception. (#2066)
 - twisted.plugin now only emits a short log message, rather than a
   full traceback, if there is a problem writing out the dropin cache
   file. (#2409)
 - Added a 'replacement' parameter to the
   'twisted.python.deprecate.deprecated' decorator.  This allows
   deprecations to unambiguously specify what they have been
   deprecated in favor of. (#3047)
 - Added access methods to FilePath for FilePath.statinfo's st_ino,
   st_dev, st_nlink, st_uid, and st_gid fields.  This is in
   preparation for the deprecation of FilePath.statinfo. (#4712)
 - IPv4Address and UNIXAddress now have a __hash__ method. (#4783)
 - twisted.protocols.ftp.FTP.ftp_STOR now catches `FTPCmdError`s
   raised by the file writer, and returns the error back to the
   client. (#4909)

Bugfixes
--------
 - twistd will no longer fail if a non-root user passes --uid 'myuid'
   as a command-line argument. Instead, it will emit an error message.
   (#3172)
 - IOCPReactor now sends immediate completions to the main loop
   (#3233)
 - trial can now load test methods from multiple classes, even if the
   methods all happen to be inherited from the same base class.
   (#3383)
 - twisted.web.server will now produce a correct Allow header when a
   particular render_FOO method is missing. (#3678)
 - HEAD requests made to resources whose HEAD handling defaults to
   calling render_GET now always receive a response with no body.
   (#3684)
 - trial now loads decorated test methods whether or not the decorator
   preserves the original method name. (#3909)
 - t.p.amp.AmpBox.serialize will now correctly consistently complain
   when being fed Unicode. (#3931)
 - twisted.internet.wxreactor now supports stopping more reliably.
   (#3948)
 - reactor.spawnProcess on Windows can now handle ASCII-encodable
   Unicode strings in the system environment (#3964)
 - When C-extensions are not complied for twisted, on python2.4, skip
   a test in twisted.internet.test.test_process that may hang due to a
   SIGCHLD related problem. Running 'python setup.py build_ext
   --inplace' will compile the extension and cause the test to both
   run and pass. (#4331)
 - twisted.python.logfile.LogFile now raises a descriptive exception
   when passed a log  directory which does not exist. (#4701)
 - Fixed a bug where Inotify will fail to add a filepatch to watchlist
   after it has been added/ignored previously. (#4708)
 - IPv4Address and UNIXAddress object comparison operators fixed
   (#4817)
 - twisted.internet.task.Clock now sorts the list of pending calls
   before and after processing each call (#4823)
 - ConnectionLost is now in twisted.internet.error.__all__ instead of
   twisted.words.protocols.jabber.xmlstream.__all__. (#4856)
 - twisted.internet.process now detects the most appropriate mechanism
   to use for detecting the open file descriptors on a system, getting
   Twisted working on FreeBSD even when fdescfs is not mounted.
   (#4881)
 - twisted.words.services referenced nonexistent
   twisted.words.protocols.irc.IRC_NOSUCHCHANNEL. This has been fixed.
   Related code has also received test cases. (#4915)

Improved Documentation
----------------------
 - The INSTALL file now lists all of Twisted's dependencies. (#967)
 - Added the stopService and startService methods to all finger
   example files. (#3375)
 - Missing reactor.run() calls were added in the UDP and client howto
   documents. (#3834)
 - The maxRetries attribute of
   twisted.internet.protocols.RetryingClientFactory now has API
   documentation. (#4618)
 - Lore docs pointed to a template that no longer existed, this has
   been fixed. (#4682)
 - The `servers` argument to `twisted.names.client.createResolver` now
   has more complete API documentation. (#4713)
 - Linked to the Twisted endpoints tutorial from the Twisted core
   howto list.  (#4773)
 - The Endpoints howto now links to the API documentation. (#4774)
 - The Quotes howto is now more clear in its PYTHONPATH setup
   instructions. (#4785)
 - The API documentation for DeferredList's fireOnOneCallback
   parameter now gives the correct order of the elements of the result
   tuple. (#4882)

Deprecations and Removals
-------------------------
 - returning a value other than None from IProtocol.dataReceived was
   deprecated (#2491)
 - Deprecated the --extra option in trial.  (#3372)
 - twisted.protocols._c_urlarg has been removed. (#4162)
 - Remove the --report-profile option for twistd, deprecated since
   2007. (#4236)
 - Deprecated twisted.persisted.journal.  This library is no longer
   maintained.  (#4298)
 - Removed twisted.protocols.loopback.loopback, which has been
   deprecated since Twisted 2.5. (#4547)
 - __getitem__ __getslice__ and __eq__ (tuple comparison, indexing)
   removed from twisted.internet.address.IPv4Address and
   twisted.internet.address.UNIXAddress classes UNIXAddress and
   IPv4Address properties _bwHack are now deprecated in
   twisted.internet.address (#4817)
 - twisted.python.reflect.allYourBase is now no longer used, replaced
   with inspect.getmro (#4928)
 - allYourBase and accumulateBases are now deprecated in favor of
   inspect.getmro. (#4946)

Other
-----

- #555, #1982, #2618, #2665, #2666, #4035, #4247, #4567, #4636,
  #4717, #4733, #4750, #4821, #4842, #4846, #4853, #4857, #4858,
  #4863, #4864, #4865, #4866, #4867, #4868, #4869, #4870, #4871,
  #4872, #4873, #4874, #4875, #4876, #4877, #4878, #4879, #4905,
  #4906, #4908, #4934, #4955, #4960


Twisted Conch 11.0.0 (2011-04-01)
=================================

Bugfixes
--------
 - The transport for subsystem protocols now declares that it
   implements ITransport and implements the getHost and getPeer
   methods. (#2453)
 - twisted.conch.ssh.transport.SSHTransportBase now responds to key
   exchange messages at any time during a connection (instead of only
   at connection setup).  It also queues non-key exchange messages
   sent during key exchange to avoid corrupting the connection state.
   (#4395)
 - Importing twisted.conch.ssh.common no longer breaks pow(base, exp[,
   modulus]) when the gmpy package is installed and base is not an
   integer. (#4803)
 - twisted.conch.ls.lsLine now returns a time string which does not
   consider the locale. (#4937)

Improved Documentation
----------------------
 - Changed the man page for ckeygen to accurately reflect what it
   does, and corrected its synopsis so that a second "ckeygen" is not
   a required part of the ckeygen command line.  (#4738)

Other
-----
 - #2112


Twisted Lore 11.0.0 (2011-04-01)
================================

No significant changes have been made for this release.


Twisted Mail 11.0.0 (2011-04-01)
================================

Features
--------
 - The `twistd mail` command line now accepts endpoint descriptions
   for POP3 and SMTP servers. (#4739)
 - The twistd mail plugin now accepts new authentication options via
   strcred.AuthOptionMixin.  These include --auth, --auth-help, and
   authentication type-specific help options. (#4740)

Bugfixes
--------
 - twisted.mail.imap4.IMAP4Server now generates INTERNALDATE strings
   which do not consider the locale. (#4937)

Improved Documentation
----------------------
 - Added a simple SMTP example, showing how to use sendmail. (#4042)

Other
-----

 - #4162


Twisted Names 11.0.0 (2011-04-01)
=================================

No significant changes have been made for this release.


Twisted News 11.0.0 (2011-04-01)
================================

No significant changes have been made for this release.

Other
-----
 - #4580


Twisted Pair 11.0.0 (2011-04-01)
================================

No significant changes have been made for this release.


Twisted Runner 11.0.0 (2011-04-01)
==================================

No significant changes have been made for this release.


Twisted Web 11.0.0 (2011-04-01)
===============================

Features
--------
 - twisted.web._newclient.HTTPParser (and therefore Agent) now handles
   HTTP headers delimited by bare LF newlines. (#3833)
 - twisted.web.client.downloadPage now accepts the `afterFoundGet`
   parameter, with the same meaning as the `getPage` parameter of the
   same name. (#4364)
 - twisted.web.xmlrpc.Proxy constructor now takes additional 'timeout'
   and 'reactor' arguments. The 'timeout' argument defaults to 30
   seconds. (#4741)
 - Twisted Web now has a templating system, twisted.web.template,
   which is a direct, simplified derivative of Divmod Nevow. (#4939)

Bugfixes
--------
 - HTTPPageGetter now adds the port to the host header if it is not
   the default for that scheme. (#3857)
 - twisted.web.http.Request.write now raises an exception if it is
   called after response generation has already finished. (#4317)
 - twisted.web.client.HTTPPageGetter and twisted.web.client.getPage
   now no longer make two requests when using afterFoundGet. (#4760)
 - twisted.web.twcgi no longer adds an extra "content-type" header to
   CGI responses. (#4786)
 - twisted.web will now properly specify an encoding (UTF-8) on error,
   redirect, and directory listing pages, so that IE7 and previous
   will not improperly guess the 'utf7' encoding in these cases.
   Please note that Twisted still sets a *default* content-type of
   'text/html', and you shouldn't rely on that: you should set the
   encoding appropriately in your application. (#4900)
 - twisted.web.http.Request.setHost now sets the port in the host
   header if it is not the default. (#4918)
 - default NOT_IMPLEMENTED and NOT_ALLOWED pages now quote the request
   method and URI respectively, to protect against browsers which
   don't quote those values for us. (#4978)

Improved Documentation
----------------------
 - The XML-RPC howto now includes an example demonstrating how to
   access the HTTP request object in a server-side XML-RPC method.
   (#4732)
 - The Twisted Web client howto now uses the correct, public name for
   twisted.web.client.Response. (#4769)
 - Some broken links were fixed, descriptions were updated, and new
   API links were added in the Resource Templating documentation
   (resource-templates.xhtml) (#4968)

Other
-----
 - #2271, #2386, #4162, #4733, #4855, #4911, #4973


Twisted Words 11.0.0 (2011-04-01)
=================================

Features
--------
 - twisted.words.protocols.irc.IRCClient now has an invite method.
   (#4820)

Bugfixes
--------
 - twisted.words.protocols.irc.IRCClient.say is once again able to
   send messages when using the default value for the length limit
   argument. (#4758)
 - twisted.words.protocols.jabber.jstrports is once again able to
   parse jstrport description strings. (#4771)
 - twisted.words.protocols.msn.NotificationClient now calls the
   loginFailure callback when it is unable to connect to the Passport
   server due to missing SSL dependencies. (#4801)
 - twisted.words.protocols.jabber.xmpp_stringprep now always uses
   Unicode version 3.2 for stringprep normalization. (#4850)

Improved Documentation
----------------------
 - Removed the non-working AIM bot example, depending on the obsolete
   twisted.words.protocols.toc functionality. (#4007)
 - Outdated GUI-related information was removed from the IM howto.
   (#4054)

Deprecations and Removals
-------------------------
 - Remove twisted.words.protocols.toc, that was largely non-working
   and useless since AOL disabled TOC on their AIM network. (#4363)

Other
-----
 - #4733, #4902


Twisted Core 10.2.0 (2010-11-29)
================================

Features
--------
 - twisted.internet.cfreactor has been significantly improved.  It now
   runs, and passes, the test suite.  Many, many bugs in it have been
   fixed, including several segfaults, as it now uses PyObjC and
   longer requires C code in Twisted. (#1833)
 - twisted.protocols.ftp.FTPRealm now accepts a parameter to override
   "/home" as the container for user directories.  The new
   BaseFTPRealm class in the same module also allows easy
   implementation of custom user directory schemes. (#2179)
 - twisted.python.filepath.FilePath and twisted.python.zippath.ZipPath
   now have a descendant method to simplify code which calls the child
   method repeatedly. (#3169)
 - twisted.python.failure._Frame objects now support fake f_locals
   attribute. (#4045)
 - twisted.internet.endpoints now has 'serverFromString' and
   'clientFromString' APIs for constructing endpoints from descriptive
   strings. (#4473)
 - The default trial reporter now combines reporting of tests with the
   same result to shorten its summary output. (#4487)
 - The new class twisted.protocols.ftp.SystemFTPRealm implements an
   FTP realm which uses system accounts to select home directories.
   (#4494)
 - twisted.internet.reactor.spawnProcess now wastes less time trying
   to close non-existent file descriptors on POSIX platforms. (#4522)
 - twisted.internet.win32eventreactor now declares that it implements
   a new twisted.internet.interfaces.IReactorWin32Events interface.
   (#4523)
 - twisted.application.service.IProcess now documents its attributes
   using zope.interface.Attribute. (#4534)
 - twisted.application.app.ReactorSelectionMixin now saves the value
   of the --reactor option in the "reactor" key of the options object.
   (#4563)
 - twisted.internet.endpoints.serverFromString and clientFromString,
   and therefore also twisted.application.strports.service, now
   support plugins, so third parties may implement their own endpoint
   types. (#4695)

Bugfixes
--------
 - twisted.internet.defer.Deferred now handles chains iteratively
   instead of recursively, preventing RuntimeError due to excessive
   recursion when handling long Deferred chains. (#411)
 - twisted.internet.cfreactor now works with trial. (#2556)
 - twisted.enterprise.adbapi.ConnectionPool.close may now be called
   even if the connection pool has not yet been started.  This will
   prevent the pool from ever starting. (#2680)
 - twisted.protocols.basic.NetstringReceiver raises
   NetstringParseErrors for  invalid netstrings now. It handles empty
   netstrings ("0:,") correctly, and  the performance for receiving
   netstrings has been improved. (#4378)
 - reactor.listenUDP now returns an object which declares that it
   implements IListeningPort. (#4462)
 - twisted.python.randbytes no longer uses PyCrypto as a secure random
   number source (since it is not one). (#4468)
 - twisted.internet.main.installReactor now blocks installation of
   another reactor when using python -O (#4476)
 - twisted.python.deprecate.deprecatedModuleAttribute now emits only
   one warning when used to deprecate a package attribute which is a
   module. (#4492)
 - The "brief" mode of twisted.python.failure.Failure.getTraceback now
   handles exceptions raised by the underlying exception's __str__
   method. (#4501)
 - twisted.words.xish.domish now correctly parses XML with namespaces
   which include whitespace. (#4503)
 - twisted.names.authority.FileAuthority now generates correct
   negative caching hints, marks its referral NS RRs as non-
   authoritative, and correctly generates referrals for ALL_RECORDS
   requests. (#4513)
 - twisted.internet.test.reactormixins.ReactorBuilder's attribute
   `requiredInterface` (which should an interface) is now
   `requiredInterfaces` (a list of interfaces) as originally described
   per the documentation. (#4527)
 - twisted.python.zippath.ZipPath.__repr__ now correctly formats paths
   with ".." in them (by including it). (#4535)
 - twisted.names.hosts.searchFileFor has been fixed against
   refcounting dependency. (#4540)
 - The POSIX process transports now declare that they implement
   IProcessTransport. (#4585)
 - Twisted can now be built with the LLVM clang compiler, with
   'CC=clang python setup.py build'.  C code that caused errors with
   this compiler has been removed. (#4652)
 - trial now puts coverage data in the path specified by --temp-
   directory, even if that option comes after --coverage on the
   command line. (#4657)
 - The unregisterProducer method of connection-oriented transports
   will now cause the connection to be closed if there was a prior
   call to loseConnection. (#4719)
 - Fixed an issue where the new StreamServerEndpointService didn't log
   listen errors.  (This was a bug not present in any previous
   releases, as this class is new.) (#4731)

Improved Documentation
----------------------
 - The trial man page now documents the meaning of the final line of
   output of the default reporter. (#1384)
 - The API documentation for twisted.internet.defer.DeferredList now
   goes into more depth about the effects each of the __init__ flags
   that class accepts. (#3595)
 - There is now narrative documentation for the endpoints APIs, in the
   'endpoints' core howto, as well as modifications to the 'writing
   clients' and 'writing servers' core howto documents to indicate
   that endpoints are now the preferred style of listening and
   connecting. (#4478)
 - trial's man page now documents the --disablegc option in more
   detail. (#4511)
 - trial's coverage output format is now documented in the trial man
   page. (#4512)
 - Broken links and spelling errors in the finger tutorial are now
   fixed. (#4516)
 - twisted.internet.threads.blockingCallFromThread's docstring is now
   explicit about Deferred support. (#4517)
 - twisted.python.zippath.ZipPath.child now documents its handling of
   ".." (which is not special, making it different from
   FilePath.child). (#4535)
 - The API docs for twisted.internet.defer.Deferred now cover several
   more of its (less interesting) attributes. (#4538)
 - LineReceiver, NetstringReceiver, and IntNStringReceiver from
   twisted.protocols.basic now have improved API documentation for
   read callbacks and write methods. (#4542)
 - Tidied up the Twisted Conch documentation for easier conversion.
   (#4566)
 - Use correct Twisted version for when cancellation was introduced in
   the Deferred docstring. (#4614)
 - The logging howto is now more clear about how the standard library
   logging module and twisted.python.log can be integrated. (#4642)
 - The finger tutorial still had references to .tap files. This
   reference has now been removed. The documentation clarifies
   "finger.tap" is a module and not a filename. (#4679)
 - The finger tutorial had a broken link to the
   twisted.application.service.Service class, which is now fixed.
   Additionally, a minor typo ('verison') was fixed.  (#4681)
 - twisted.protocols.policies.TimeoutMixin now has clearer API
   documentation. (#4684)

Deprecations and Removals
-------------------------
 - twisted.internet.defer.Deferred.setTimeout has been removed, after
   being deprecated since Twisted 2.0. (#1702)
 - twisted.internet.interfaces.IReactorTime.cancelCallLater
   (deprecated since  2007) and
   twisted.internet.interfaces.base.ReactorBase.cancelCallLater
   (deprecated since 2002) have been removed. (#4076)
 - Removed twisted.cred.util.py, which has been deprecated since
   Twisted 8.3. (#4107)
 - twisted.python.text.docstringLStrip was deprecated. (#4328)
 - The module attributes `LENGTH`, `DATA`, `COMMA`, and `NUMBER` of
   twisted.protocols.basic (previously used by `NetstringReceiver`)
   are now deprecated. (#4541)
 - twisted.protocols.basic.SafeNetstringReceiver, deprecated since
   2001 (before Twisted 2.0), was removed. (#4546)
 - twisted.python.threadable.whenThreaded, deprecated since Twisted
   2.2.0, has been removed. (#4550)
 - twisted.python.timeoutqueue, deprecated since Twisted 8.0, has been
   removed. (#4551)
 - iocpreactor transports can no longer be pickled. (#4617)

Other
-----
 - #4300, #4475, #4477, #4504, #4556, #4562, #4564, #4569, #4608,
   #4616, #4617, #4626, #4630, #4650, #4705


Twisted Conch 10.2.0 (2010-11-29)
=================================

Bugfixes
--------
 - twisted.conch.ssh.factory.SSHFactory no longer disables coredumps.
   (#2715)
 - The Deferred returned by twisted.conch.telnet.TelnetTransport.will
   now fires with an OptionRefused failure if the peer responds with a
   refusal for the option negotiation. (#4231)
 - SSHServerTransport and SSHClientTransport in
   twisted.conch.ssh.transport no longer use PyCrypto to generate
   random numbers for DH KEX.  They also now generate values from the
   full valid range, rather than only half of it. (#4469)
 - twisted.conch.ssh.connection.SSHConnection now errbacks leftover
   request deferreds on connection shutdown. (#4483)

Other
-----
 - #4677


Twisted Lore 10.2.0 (2010-11-29)
================================

No significant changes have been made for this release.

Other
-----
 - #4571


Twisted Mail 10.2.0 (2010-11-29)
================================

Improved Documentation
----------------------
 - The email server example now demonstrates how to set up
   authentication and authorization using twisted.cred. (#4609)

Deprecations and Removals
-------------------------
 - twisted.mail.smtp.sendEmail, deprecated since mid 2003 (before
   Twisted 2.0), has been removed. (#4529)

Other
-----
 - #4038, #4572


Twisted Names 10.2.0 (2010-11-29)
=================================

Features
--------
 - twisted.names.server can now serve SPF resource records using
   twisted.names.dns.Record_SPF.  twisted.names.client can query for
   them using lookupSenderPolicy.   (#3928)

Bugfixes
--------
 - twisted.names.common.extractRecords doesn't try to close the
   transport anymore in case of recursion, as it's done by the
   Resolver itself now. (#3998)

Improved Documentation
----------------------
 - Tidied up the Twisted Names documentation for easier conversion.
   (#4573)


Twisted News 10.2.0 (2010-11-29)
================================

Bugfixes
--------
 - twisted.news.database.PickleStorage now invokes the email APIs
   correctly, allowing it to actually send moderation emails. (#4528)


Twisted Pair 10.2.0 (2010-11-29)
================================

No significant changes have been made for this release.


Twisted Runner 10.2.0 (2010-11-29)
==================================

No significant changes have been made for this release.


Twisted Web 10.2.0 (2010-11-29)
===============================

Features
--------
 - twisted.web.xmlrpc.XMLRPC.xmlrpc_* methods can now be decorated
   using withRequest to cause them to be passed the HTTP request
   object. (#3073)

Bugfixes
--------
 - twisted.web.xmlrpc.QueryProtocol.handleResponse now disconnects
   from the server, meaning that Twisted XML-RPC clients disconnect
   from the server as soon as they receive a response, rather than
   relying on the server to disconnect. (#2518)
 - twisted.web.twcgi now generates responses containing all
   occurrences of duplicate headers produced by CGI scripts, not just
   the last value. (#4742)

Deprecations and Removals
-------------------------
 - twisted.web.trp, which has been deprecated since Twisted 9.0, was
   removed. (#4299)

Other
-----
 - #4576, #4577, #4709, #4723


Twisted Words 10.2.0 (2010-11-29)
=================================

Features
--------
 - twisted.words.protocols.irc.IRCClient.msg now enforces a maximum
   length for messages, splitting up messages that are too long.
   (#4416)

Bugfixes
--------
 - twisted.words.protocols.irc.IRCClient no longer invokes privmsg()
   in the default noticed() implementation. (#4419)
 - twisted.words.im.ircsupport.IRCProto now sends the correct name in
   the USER command. (#4641)

Deprecations and Removals
-------------------------
 - Remove twisted.words.im.proxyui and twisted.words.im.tap. (#1823)


Twisted Core 10.1.0 (2010-06-27)
================================

Features
--------
 - Add linux inotify support, allowing monitoring of file system
   events. (#972)
 - Deferreds now support cancellation. (#990)
 - Added new "endpoint" interfaces in twisted.internet.interfaces,
   which abstractly describe stream transport endpoints which can be
   listened on or connected to.  Implementations for TCP and SSL
   clients and servers are present in twisted.internet.endpoints.
   Notably, client endpoints' connect() methods return cancellable
   Deferreds, so code written to use them can bypass the awkward
   "ClientFactory.clientConnectionFailed" and
   "Connector.stopConnecting" methods, and handle errbacks from or
   cancel the returned deferred, respectively. (#1442)
 - twisted.protocols.amp.Integer's documentation now clarifies that
   integers of arbitrary size are supported and that the wire format
   is a base-10 representation. (#2650)
 - twisted.protocols.amp now includes support for transferring
   timestamps (amp.DateTime) and decimal values (amp.Decimal). (#2651)
 - twisted.protocol.ftp.IWriteFile now has a close() method, which can
   return a Deferred. Previously a STOR command would finish
   immediately upon the receipt of the last byte of the uploaded file.
   With close(), the backend can delay the finish until it has
   performed some other slow action (like storing the data to a
   virtual filesystem). (#3462)
 - FilePath now calls os.stat() only when new status information is
   required, rather than immediately when anything changes.  For some
   applications this may result in fewer stat() calls.  Additionally,
   FilePath has a new method, 'changed', which applications may use to
   indicate that the FilePath may have been changed on disk and
   therefore the next status information request must  fetch a new
   stat result.  This is useful if external systems, such as C
   libraries, may have changed files that Twisted applications are
   referencing via a FilePath. (#4130)
 - Documentation improvements are now summarized in the NEWS file.
   (#4224)
 - twisted.internet.task.deferLater now returns a cancellable
   Deferred. (#4318)
 - The connect methods of twisted.internet.protocol.ClientCreator now
   return cancellable Deferreds. (#4329)
 - twisted.spread.pb now has documentation covering some of its
   limitations. (#4402)
 - twisted.spread.jelly now supports jellying and unjellying classes
   defined with slots if they also implement __getstate__ and
   __setstate__. (#4430)
 - twisted.protocols.amp.ListOf arguments can now be specified as
   optional. (#4474)

Bugfixes
--------
 - On POSIX platforms, reactors now support child processes in a way
   which doesn't cause other syscalls to sometimes fail with EINTR (if
   running on Python 2.6 or if Twisted's extension modules have been
   built). (#733)
 - Substrings are escaped before being passed to a regular expression
   for searching to ensure that they don't get interpreted as part of
   the expression. (#1893)
 - twisted.internet.stdio now supports stdout being redirected to a
   normal file (except when using epollreactor). (#2259)
 -  (#2367)
 - The tap2rpm script now works with modern versions of RPM. (#3292)
 - twisted.python.modules.walkModules will now handle packages
   explicitly precluded from importing by a None placed in
   sys.modules. (#3419)
 - ConnectedDatagramPort now uses stopListening when a connection
   fails instead of the deprecated loseConnection. (#3425)
 - twisted.python.filepath.FilePath.setContent is now safe for
   multiple processes to use concurrently. (#3694)
 - The mode argument to the methods of
   twisted.internet.interfaces.IReactorUNIX is no longer deprecated.
   (#4078)
 - Do not include blacklisted projects when generating NEWS. (#4190)
 - When generating NEWS for a project that had no significant changes,
   include a section for that project and say that there were no
   interesting changes. (#4191)
 - Redundant 'b' mode is no longer passed to calls to FilePath.open
   and FilePath.open itself now corrects the mode when multiple 'b'
   characters are present, ensuring only one instance of 'b' is
   provided, as a workaround for http://bugs.python.org/issue7686.
   (#4207)
 - HTML tags inside <pre> tags in the code snippets are now escaped.
   (#4336)
 - twisted.protocols.amp.CommandLocator now allows subclasses to
   override responders inherited from base classes. (#4343)
 - Fix a bunch of small but important defects in the INSTALL, README
   and so forth. (#4346)
 - The poll, epoll, glib2, and gtk2 reactors now all support half-
   close in the twisted.internet.stdio.StandardIO transport. (#4352)
 - twisted.application.internet no longer generates an extra and
   invalid entry in its __all__ list for the nonexistent
   MulticastClient. (#4373)
 - Choosing a reactor documentation now says that only the select-
   based reactor is a truly cross-platform reactor. (#4384)
 - twisted.python.filepath.FilePath now no longer leaves files open,
   to be closed by the garbage collector, when an exception is raised
   in the implementation of setContent, getContent, or copyTo. (#4400)
 - twisted.test.proto_helpers.StringTransport's getHost and getPeer
   methods now return IPv4Address instances by default. (#4401)
 - twisted.protocols.amp.BinaryBoxProtocol will no longer deliver an
   empty string to a switched-to protocol's dataReceived method when
   the BinaryBoxProtocol's buffer happened to be empty at the time of
   the protocol switch. (#4405)
 - IReactorUNIX.listenUNIX implementations now support abstract
   namespace sockets on Linux. (#4421)
 - Files opened with FilePath.create() (and therefore also files
   opened via FilePath.open() on a path with alwaysCreate=True) will
   now be opened in binary mode as advertised, so that they will
   behave portably across platforms. (#4453)
 - The subunit reporter now correctly reports import errors as errors,
   rather than by crashing with an unrelated error. (#4496)

Improved Documentation
----------------------
 - The finger tutorial example which introduces services now avoids
   double-starting the loop to re-read its users file. (#4420)
 - twisted.internet.defer.Deferred.callback's docstring now mentions
   the implicit chaining feature. (#4439)
 - doc/core/howto/listing/pb/chatclient.py can now actually send a
   group message. (#4459)

Deprecations and Removals
-------------------------
 - twisted.internet.interfaces.IReactorArbitrary,
   twisted.application.internet.GenericServer, and
   twisted.application.internet.GenericClient are now deprecated.
   (#367)
 - twisted.internet.gtkreactor is now deprecated. (#2833)
 - twisted.trial.util.findObject has been deprecated. (#3108)
 - twisted.python.threadpool.ThreadSafeList is deprecated and Jython
   platform detection in Twisted core removed (#3725)
 - twisted.internet.interfaces.IUDPConnectedTransport has been removed
   (deprecated since Twisted 9.0). (#4077)
 - Removed twisted.application.app.runWithProfiler, which has been
   deprecated since Twisted 8.0. (#4090)
 - Removed twisted.application.app.runWithHotshot, which has been
   deprecated since Twisted 8.0. (#4091)
 - Removed twisted.application.app.ApplicationRunner.startLogging,
   which has been deprecated (doesn't say since when), as well as
   support for the legacy
   twisted.application.app.ApplicationRunner.getLogObserver method.
   (#4092)
 - twisted.application.app.reportProfile has been removed. (#4093)
 - twisted.application.app.getLogFile has been removed. (#4094)
 - Removed twisted.cred.util.py, which has been deprecated since
   Twisted 8.3. (#4107)
 - twisted.python.util.dsu is now deprecated. (#4339)
 - In twisted.trial.util: FailureError, DirtyReactorWarning,
   DirtyReactorError, and PendingTimedCallsError, which have all been
   deprecated since Twisted 8.0, have been removed. (#4505)

Other
-----
 - #1363, #1742, #3170, #3359, #3431, #3738, #4088, #4206, #4221,
   #4239, #4257, #4272, #4274, #4287, #4291, #4293, #4309, #4316,
   #4319, #4324, #4332, #4335, #4348, #4358, #4394, #4399, #4409,
   #4418, #4443, #4449, #4479, #4485, #4486, #4497


Twisted Conch 10.1.0 (2010-06-27)
=================================

Features
--------
 - twisted.conch.ssh.transport.SSHTransportBase now allows supported
   ssh protocol versions to be overridden. (#4428)

Bugfixes
--------
 - SSHSessionProcessProtocol now doesn't close the session when stdin
   is closed, but instead when both stdout and stderr are. (#4350)
 - The 'cftp' command-line tool will no longer encounter an
   intermittent error, crashing at startup with a ZeroDivisionError
   while trying to report progress. (#4463)
 - twisted.conch.ssh.connection.SSHConnection now replies to requests
   to open an unknown channel with an OPEN_UNKNOWN_CHANNEL_TYPE message
   instead of closing the connection. (#4490)

Deprecations and Removals
-------------------------
 - twisted.conch.insults.client was deprecated. (#4095)
 - twisted.conch.insults.colors has been deprecated.  Please use
   twisted.conch.insults.helper instead. (#4096)
 - Removed twisted.conch.ssh.asn1, which has been deprecated since
   Twisted 9.0. (#4097)
 - Removed twisted.conch.ssh.common.Entropy, as Entropy.get_bytes has
   been  deprecated since 2007 and Entropy.get_bytes was the only
   attribute of Entropy. (#4098)
 - Removed twisted.conch.ssh.keys.getPublicKeyString, which has been
   deprecated since 2007.  Also updated the conch examples
   sshsimpleserver.py and sshsimpleclient.py to reflect this removal.
   (#4099)
 - Removed twisted.conch.ssh.keys.makePublicKeyString, which has been
   deprecated since 2007. (#4100)
 - Removed twisted.conch.ssh.keys.getPublicKeyObject, which has been
   deprecated since 2007. (#4101)
 - Removed twisted.conch.ssh.keys.getPrivateKeyObject, which has been
   deprecated since 2007.  Also updated the conch examples to reflect
   this removal. (#4102)
 - Removed twisted.conch.ssh.keys.makePrivateKeyString, which has been
   deprecated since 2007. (#4103)
 - Removed twisted.conch.ssh.keys.makePublicKeyBlob, which has been
   deprecated since 2007. (#4104)
 - Removed twisted.conch.ssh.keys.signData,
   twisted.conch.ssh.keys.verifySignature, and
   twisted.conch.ssh.keys.printKey, which have been deprecated since
   2007.   (#4105)

Other
-----
 - #3849, #4408, #4454


Twisted Lore 10.1.0 (2010-06-27)
================================

No significant changes have been made for this release.


Twisted Mail 10.1.0 (2010-06-27)
================================

Bugfixes
--------
 - twisted.mail.imap4.IMAP4Server no longer fails on search queries
   that contain wildcards. (#2278)
 - A case which would cause twisted.mail.imap4.IMAP4Server to loop
   indefinitely when handling a search command has been fixed. (#4385)

Other
-----
 - #4069, #4271, #4467


Twisted Names 10.1.0 (2010-06-27)
=================================

Features
--------
 - twisted.names.dns.Message now uses a specially constructed
   dictionary for looking up record types.  This yields a significant
   performance improvement on PyPy. (#4283)


Twisted News 10.1.0 (2010-06-27)
================================

No significant changes have been made for this release.


Twisted Pair 10.1.0 (2010-06-27)
================================

No significant changes have been made for this release.


Twisted Runner 10.1.0 (2010-06-27)
==================================

Features
--------
 - twistd now has a procmon subcommand plugin - a convenient way to
   monitor and automatically restart another process. (#4356)

Deprecations and Removals
-------------------------
 - twisted.runner.procmon.ProcessMonitor's active, consistency, and
   consistencyDelay attributes are now deprecated. (#1763)

Other
-----
 - #3775


Twisted Web 10.1.0 (2010-06-27)
===============================

Features
--------
 - twisted.web.xmlrpc.XMLRPC and twisted.web.xmlrpc.Proxy now expose
   xmlrpclib's support of datetime.datetime objects if useDateTime is
   set to True. (#3219)
 - HTTP11ClientProtocol now has an abort() method for cancelling an
   outstanding request by closing the connection before receiving the
   entire response. (#3811)
 - twisted.web.http_headers.Headers initializer now rejects
   incorrectly structured dictionaries. (#4022)
 - twisted.web.client.Agent now supports HTTPS URLs. (#4023)
 - twisted.web.xmlrpc.Proxy.callRemote now returns a Deferred which
   can be cancelled to abort the attempted XML-RPC call. (#4377)

Bugfixes
--------
 - twisted.web.guard now logs out avatars even if a request completes
   with an error. (#4411)
 - twisted.web.xmlrpc.XMLRPC will now no longer trigger a RuntimeError
   by trying to write responses to closed connections. (#4423)

Improved Documentation
----------------------
 - Fix broken links to deliverBody and iweb.UNKNOWN_LENGTH in
   doc/web/howto/client.xhtml. (#4507)

Deprecations and Removals
-------------------------
 - twisted.web.twcgi.PHP3Script and twisted.web.twcgi.PHPScript are
   now deprecated. (#516)

Other
-----
 - #4403, #4452


Twisted Words 10.1.0 (2010-06-27)
=================================

Bugfixes
--------
 - twisted.words.im.basechat.ChatUI now has a functional
   contactChangedNick with unit tests. (#229)
 - twisted.words.protocols.jabber.error.StanzaError now correctly sets
   a default error type and code for the remote-server-timeout
   condition (#4311)
 - twisted.words.protocols.jabber.xmlstream.ListenAuthenticator now
   uses unicode objects for session identifiers (#4345)


Twisted Core 10.0.0 (2010-03-01)
================================

Features
--------
 - The twistd man page now has a SIGNALS section. (#689)

 - reactor.spawnProcess now will not emit a PotentialZombieWarning
   when called before reactor.run, and there will be no potential for
   zombie processes in this case. (#2078)

 - High-throughput applications based on Perspective Broker should now
   run noticeably faster thanks to the use of a more efficient decoding
   function in Twisted Spread. (#2310)

 - Documentation for trac-post-commit-hook functionality in svn-dev
   policy. (#3867)

 - twisted.protocols.socks.SOCKSv4 now supports the SOCKSv4a protocol.
   (#3886)

 - Trial can now output test results according to the subunit
   protocol, as long as Subunit is installed (see
   https://launchpad.net/subunit). (#4004)

 - twisted.protocols.amp now provides a ListOf argument type which can
   be composed with some other argument types to create a zero or more
   element sequence of that type. (#4116)

 - If returnValue is invoked outside of a function decorated with
   @inlineCallbacks, but causes a function thusly decorated to exit, a
   DeprecationWarning will be emitted explaining this potentially
   confusing behavior.  In a future release, this will cause an
   exception. (#4157)

 - twisted.python.logfile.BaseLogFile now has a reopen method allowing
   you to use an external logrotate mechanism. (#4255)

Bugfixes
--------
 - FTP.ftp_NLST now handles requests on invalid paths in a way
   consistent with RFC 959. (#1342)

 - twisted.python.util.initgroups now calls the low-level C initgroups
   by default if available: the python version can create lots of I/O
   with certain authentication setup to retrieve all the necessary
   information. (#3226)

 - startLogging now does nothing on subsequent invocations, thus
   fixing a terrible infinite recursion bug that's only on edge case.
   (#3289)

 - Stringify non-string data to NetstringReceiver.sendString before
   calculating the length so that the calculated length is equal to
   the actual length of the transported data. (#3299)

 - twisted.python.win32.cmdLineQuote now correctly quotes empty
   strings arguments (#3876)

 - Change the behavior of the Gtk2Reactor to register only one source
   watch for each file descriptor, instead of one for reading and one
   for writing. In particular, it fixes a bug with Glib under Windows
   where we failed to notify when a client is connected. (#3925)

 - Twisted Trial no longer crashes if it can't remove an old
   _trial_temp directory.  (#4020)

 - The optional _c_urlarg extension now handles unquote("") correctly
   on platforms where malloc(0) returns NULL, such as AIX.  It also
   compiles with less warnings. (#4142)

 - On POSIX, child processes created with reactor.spawnProcess will no
   longer automatically ignore the signals which the parent process
   has set to be ignored. (#4199)

 - All SOCKSv4a tests now use a dummy reactor with a deterministic
   resolve method. (#4275)

 - Prevent extraneous server, date and content-type headers in proxy
   responses. (#4277)

Deprecations and Removals
-------------------------
 - twisted.internet.error.PotentialZombieWarning is now deprecated.
   (#2078)

 - twisted.test.time_helpers is now deprecated. (#3719)

 - The deprecated connectUDP method of IReactorUDP has now been
   removed. (#4075)

 - twisted.trial.unittest.TestCase now ignores the previously
   deprecated setUpClass and tearDownClass methods. (#4175)

Other
-----
 - #917, #2406, #2481, #2608, #2689, #2884, #3056, #3082, #3199,
   #3480, #3592, #3718, #3935, #4066, #4083, #4154, #4166, #4169,
   #4176, #4183, #4186, #4188, #4189, #4194, #4201, #4204, #4209,
   #4222, #4234, #4235, #4238, #4240, #4245, #4251, #4264, #4268,
   #4269, #4282


Twisted Conch 10.0.0 (2010-03-01)
=================================

Bugfixes
--------
 - twisted.conch.checkers.SSHPublicKeyDatabase now looks in the
   correct user directory for authorized_keys files. (#3984)
 - twisted.conch.ssh.SSHUserAuthClient now honors preferredOrder when
   authenticating. (#4266)

Other
-----
 - #2391, #4203, #4265


Twisted Lore 10.0.0 (2010-03-01)
================================

Other
-----
 - #4241


Twisted Mail 10.0.0 (2010-03-01)
================================

Bugfixes
--------
 - twisted.mail.smtp.ESMTPClient and
   twisted.mail.smtp.LOGINAuthenticator now implement the (obsolete)
   LOGIN SASL mechanism according to the draft specification. (#4031)

 - twisted.mail.imap4.IMAP4Client will no longer misparse all html-
   formatted message bodies received in response to a fetch command.
   (#4049)

 - The regression in IMAP4 search handling of "OR" and "NOT" terms has
   been fixed. (#4178)

Other
-----
 - #4028, #4170, #4200


Twisted Names 10.0.0 (2010-03-01)
=================================

Bugfixes
--------
 - twisted.names.root.Resolver no longer leaks UDP sockets while
   resolving names. (#970)

Deprecations and Removals
-------------------------
 - Several top-level functions in twisted.names.root are now
   deprecated. (#970)

Other
-----
 - #4066


Twisted Pair 10.0.0 (2010-03-01)
================================

Other
-----
 - #4170


Twisted Runner 10.0.0 (2010-03-01)
==================================

Other
-----
 - #3961


Twisted Web 10.0.0 (2010-03-01)
===============================

Features
--------
 - Twisted Web in 60 Seconds, a series of short tutorials with self-
   contained examples on a range of common web topics, is now a part
   of the Twisted Web howto documentation. (#4192)

Bugfixes
--------
 - Data and File from twisted.web.static and
   twisted.web.distrib.UserDirectory will now only generate a 200
   response for GET or HEAD requests.
   twisted.web.client.HTTPPageGetter will no longer ignore the case of
   a request method when considering whether to apply special HEAD
   processing to a response. (#446)

 - twisted.web.http.HTTPClient now supports multi-line headers.
   (#2062)

 - Resources served via twisted.web.distrib will no longer encounter a
   Banana error when writing more than 640kB at once to the request
   object. (#3212)

 - The Error, PageRedirect, and InfiniteRedirection exception in
   twisted.web now initialize an empty message parameter by mapping
   the HTTP status code parameter to a descriptive string. Previously
   the lookup would always fail, leaving message empty.  (#3806)

 - The 'wsgi.input' WSGI environment object now supports -1 and None
   as arguments to the read and readlines methods. (#4114)

 - twisted.web.wsgi doesn't unquote QUERY_STRING anymore, thus
   complying with the WSGI reference implementation. (#4143)

 - The HTTP proxy will no longer pass on keep-alive request headers
   from the client, preventing pages from loading then "hanging"
   (leaving the connection open with no hope of termination). (#4179)

Deprecations and Removals
-------------------------
 - Remove '--static' option from twistd web, that served as an alias
   for the '--path' option. (#3907)

Other
-----
 - #3784, #4216, #4242


Twisted Words 10.0.0 (2010-03-01)
=================================

Features
--------
 - twisted.words.protocols.irc.IRCClient.irc_MODE now takes ISUPPORT
   parameters into account when parsing mode messages with arguments
   that take parameters (#3296)

Bugfixes
--------
 - When twisted.words.protocols.irc.IRCClient's versionNum and
   versionEnv attributes are set to None, they will no longer be
   included in the client's response to CTCP VERSION queries. (#3660)

 - twisted.words.protocols.jabber.xmlstream.hashPassword now only
   accepts unicode as input (#3741, #3742, #3847)

Other
-----
 - #2503, #4066, #4261


Twisted Core 9.0.0 (2009-11-24)
===============================

Features
--------
 - LineReceiver.clearLineBuffer now returns the bytes that it cleared (#3573)
 - twisted.protocols.amp now raises InvalidSignature when bad arguments are
   passed to Command.makeArguments (#2808)
 - IArgumentType was added to represent an existing but previously unspecified
   interface in amp (#3468)
 - Obscure python tricks have been removed from the finger tutorials (#2110)
 - The digest auth implementations in twisted.web and twisted.protocolos.sip
   have been merged together in twisted.cred (#3575)
 - FilePath and ZipPath now has a parents() method which iterates up all of its
   parents (#3588)
 - reactors which support threads now have a getThreadPool method (#3591)
 - The MemCache client implementation now allows arguments to the "stats"
   command (#3661)
 - The MemCache client now has a getMultiple method which allows fetching of
   multiple values (#3171)
 - twisted.spread.jelly can now unserialize some new-style classes (#2950)
 - twisted.protocols.loopback.loopbackAsync now accepts a parameter to control
   the data passed between client and server (#3820)
 - The IOCP reactor now supports SSL (#593)
 - Tasks in a twisted.internet.task.Cooperator can now be paused, resumed, and
   cancelled (#2712)
 - AmpList arguments can now be made optional (#3891)
 - The syslog output observer now supports log levels (#3300)
 - LoopingCall now supports reporting the number of intervals missed if it
   isn't able to schedule calls fast enough (#3671)

Fixes
-----
 - The deprecated md5 and sha modules are no longer used if the stdlib hashlib
   module is available (#2763)
 - An obscure deadlock involving waking up the reactor within signal handlers
   in particular threads was fixed (#1997)
 - The passivePortRange attribute of FTPFactory is now honored (#3593)
 - TestCase.flushWarnings now flushes warnings even if they were produced by a
   file that was renamed since it was byte compiled (#3598)
 - Some internal file descriptors are now marked as close-on-exec, so these will
   no longer be leaked to child processes (#3576)
 - twisted.python.zipstream now correctly extracts the first file in a directory
   as a file, and not an empty directory (#3625)
 - proxyForInterface now returns classes which correctly *implement* interfaces
   rather than *providing* them (#3646)
 - SIP Via header parameters should now be correctly generated (#2194)
 - The Deferred returned by stopListening would sometimes previously never fire
   if an exception was raised by the underlying file descriptor's connectionLost
   method. Now the Deferred will fire with a failure (#3654)
 - The command-line tool "manhole" should now work with newer versions of pygtk
   (#2464)
 - When a DefaultOpenSSLContextFactory is instantiated with invalid parameters,
   it will now raise an exception immediately instead of waiting for the first
   connection (#3700)
 - Twisted command line scripts should now work when installed in a virtualenv
   (#3750)
 - Trial will no longer delete temp directories which it did not create (#3481)
 - Processes started on Windows should now be cleaned up properly in more cases
   (#3893)
 - Certain misbehaving importers will no longer cause twisted.python.modules
   (and thus trial) to raise an exception, but rather issue a warning (#3913)
 - MemCache client protocol methods will now fail when the transport has been
   disconnected (#3643)
 - In the AMP method callRemoteString, the requiresAnswer parameter is now
   honored (#3999)
 - Spawning a "script" (a file which starts with a #! line) on Windows running
   Python 2.6 will now work instead of raising an exception about file mode
   "ru" (#3567)
 - FilePath's walk method now calls its "descend" parameter even on the first
   level of children, instead of only on grandchildren. This allows for better
   symlink cycle detection (#3911)
 - Attempting to write unicode data to process pipes on Windows will no longer
   result in arbitrarily encoded messages being written to the pipe, but instead
   will immediately raise an error (#3930)
 - The various twisted command line utilities will no longer print
   ModuleType.__doc__ when Twisted was installed with setuptools (#4030)
 - A Failure object will now be passed to connectionLost on stdio connections
   on Windows, instead of an Exception object (#3922)

Deprecations and Removals
-------------------------
 - twisted.persisted.marmalade was deleted after a long period of deprecation
   (#876)
 - Some remaining references to the long-gone plugins.tml system were removed
   (#3246)
 - SSLv2 is now disabled by default, but it can be re-enabled explicitly
   (#3330)
 - twisted.python.plugin has been removed (#1911)
 - reactor.run will now raise a ReactorAlreadyRunning exception when it is
   called reentrantly instead of warning a DeprecationWarning (#1785)
 - twisted.spread.refpath is now deprecated because it is unmaintained,
   untested, and has dubious value (#3723)
 - The unused --quiet flag has been removed from the twistd command (#3003)

Other
-----
 - #3545, #3490, #3544, #3537, #3455, #3315, #2281, #3564, #3570, #3571, #3486,
   #3241, #3599, #3220, #1522, #3611, #3596, #3606, #3609, #3602, #3637, #3647,
   #3632, #3675, #3673, #3686, #2217, #3685, #3688, #2456, #506, #3635, #2153,
   #3581, #3708, #3714, #3717, #3698, #3747, #3704, #3707, #3713, #3720, #3692,
   #3376, #3652, #3695, #3735, #3786, #3783, #3699, #3340, #3810, #3822, #3817,
   #3791, #3859, #2459, #3677, #3883, #3894, #3861, #3822, #3852, #3875, #2722,
   #3768, #3914, #3885, #2719, #3905, #3942, #2820, #3990, #3954, #1627, #2326,
   #2972, #3253, #3937, #4058, #1200, #3639, #4079, #4063, #4050


Twisted Conch 9.0.0 (2009-11-24)
================================

Fixes
-----
 - The SSH key parser has been removed and conch now uses pyASN1 to parse keys.
   This should fix a number of cases where parsing a key would fail, but it now
   requires users to have pyASN1 installed (#3391)
 - The time field on SFTP file listings should now be correct (#3503)
 - The day field on SFTP file listings should now be correct on Windows (#3503)
 - The "cftp" sftp client now truncates files it is uploading over (#2519)
 - The telnet server protocol can now properly respond to subnegotiation
   requests (#3655)
 - Tests and factoring of the SSHv2 server implementation are now much better
   (#2682)
 - The SSHv2 server now sends "exit-signal" messages to the client, instead of
   raising an exception, when a process dies due to a signal (#2687)
 - cftp's client-side "exec" command now uses /bin/sh if the current user has
   no shell (#3914)

Deprecations and Removals
-------------------------
 - The buggy SSH connection sharing feature of the SSHv2 client was removed
   (#3498)
 - Use of strings and PyCrypto objects to represent keys is deprecated in favor
   of using Conch Key objects (#2682)

Other
-----
 - #3548, #3537, #3551, #3220, #3568, #3689, #3709, #3809, #2763, #3540, #3750,
   #3897, #3813, #3871, #3916, #4047, #3940, #4050


Twisted Lore 9.0.0 (2009-11-24)
===============================

Features
--------
 - Python source listings now include line numbers (#3486)

Fixes
-----
 - Lore now uses minidom instead of Twisted's microdom, which incidentally
   fixes some Lore bugs such as throwing away certain whitespace
   (#3560, #414, #3619)
 - Lore's "lint" command should no longer break on documents with links in them
   (#4051, #4115)

Deprecations and Removals
-------------------------
 - Lore no longer uses the ancient "tml" Twisted plugin system (#1911)

Other
-----
 - #3565, #3246, #3540, #3750, #4050


Twisted Mail 9.0.0 (2009-11-24)
===============================

Features
--------
 - maildir.StringListMailbox, an in-memory maildir mailbox, now supports
   deletion, undeletion, and syncing (#3547)
 - SMTPClient's callbacks are now more completely documented (#684)

Fixes
-----
 - Parse UNSEEN response data and include it in the result of
   IMAP4Client.examine (#3550)
 - The IMAP4 client now delivers more unsolicited server responses to callbacks
   rather than ignoring them, and also won't ignore solicited responses that
   arrive on the same line as an unsolicited one (#1105)
 - Several bugs in the SMTP client's idle timeout support were fixed (#3641,
   #1219)
 - A case where the SMTP client could skip some recipients when retrying
   delivery has been fixed (#3638)
 - Errors during certain data transfers will no longer be swallowed. They will
   now bubble up to the higher-level API (such as the sendmail function) (#3642)
 - Escape sequences inside quoted strings in IMAP4 should now be parsed
   correctly by the IMAP4 server protocol (#3659)
 - The "imap4-utf-7" codec that is registered by twisted.mail.imap4 had a number
   of fixes that allow it to work better with the Python codecs system, and to
   actually work (#3663)
 - The Maildir implementation now ensures time-based ordering of filenames so
   that the lexical sorting of messages matches the order in which they were
   received (#3812)
 - SASL PLAIN credentials generated by the IMAP4 protocol implementations
   (client and server) should now be RFC-compliant (#3939)
 - Searching for a set of sequences using the IMAP4 "SEARCH" command should
   now work on the IMAP4 server protocol implementation. This at least improves
   support for the Pine mail client (#1977)

Other
-----
 - #2763, #3647, #3750, #3819, #3540, #3846, #2023, #4050


Twisted Names 9.0.0 (2009-11-24)
================================

Deprecations and Removals
-------------------------
 - client.ThreadedResolver is deprecated in favor of
   twisted.internet.base.ThreadedResolver (#3710)

Other
-----
 - #3540, #3560, #3712, #3750, #3990


Twisted News 9.0.0 (2009-11-24)
===============================

Other
-----
 - #2763, #3540


Twisted Pair 9.0.0 (2009-11-24)
===============================

Other
-----
 - #3540, #4050


Twisted Runner 9.0.0 (2009-11-24)
=================================

Features
--------
 - procmon.ProcessMonitor.addProcess now accepts an 'env' parameter which allows
   users to specify the environment in which a process will be run (#3691)

Other
-----
 - #3540


Twisted Web 9.0.0 (2009-11-24)
==============================

Features
--------
 - There is now an iweb.IRequest interface which specifies the interface that
   request objects provide (#3416)
 - downloadPage now supports the same cookie, redirect, and timeout features
   that getPage supports (#2971)
 - A chapter about WSGI has been added to the twisted.web documentation (#3510)
 - The HTTP auth support in the web server now allows anonymous sessions by
   logging in with ANONYMOUS credentials when no Authorization header is
   provided in a request (#3924, #3936)
 - HTTPClientFactory now accepts a parameter to enable a common deviation from
   the HTTP 1.1 standard by responding to redirects in a POSTed request with a
   GET instead of another POST (#3624)
 - A new basic HTTP/1.1 client API is included in twisted.web.client.Agent
   (#886, #3987)

Fixes
-----
 - Requests for "insecure" children of a static.File (such as paths containing
   encoded directory separators) will now result in a 404 instead of a 500
   (#3549, #3469)
 - When specifying a followRedirect argument to the getPage function, the state
   of redirect-following for other getPage calls should now be unaffected.  It
   was previously overwriting a class attribute which would affect outstanding
   getPage calls (#3192)
 - Downloading an URL of the form "http://example.com:/" will now work,
   ignoring the extraneous colon (#2402)
 - microdom's appendChild method will no longer issue a spurious warning, and
   microdom's methods in general should now issue more meaningful exceptions
   when invalid parameters are passed (#3421)
 - WSGI applications will no longer have spurious Content-Type headers added to
   their responses by the twisted.web server. In addition, WSGI applications
   will no longer be able to specify the server-restricted headers Server and
   Date (#3569)
 - http_headers.Headers now normalizes the case of raw headers passed directly
   to it in the same way that it normalizes the headers passed to setRawHeaders
   (#3557)
 - The distrib module no longer relies on the deprecated woven package (#3559)
 - twisted.web.domhelpers now works with both microdom and minidom (#3600)
 - twisted.web servers will now ignore invalid If-Modified-Since headers instead
   of returning a 500 error (#3601)
 - Certain request-bound memory and file resources are cleaned up slightly
   sooner by the request when the connection is lost (#1621, #3176)
 - xmlrpclib.DateTime objects should now correctly round-trip over twisted.web's
   XMLRPC support in all supported versions of Python, and errors during error
   serialization will no longer hang a twisted.web XMLRPC response (#2446)
 - request.content should now always be seeked to the beginning when
   request.process is called, so application code should never need to seek
   back manually (#3585)
 - Fetching a child of static.File with a double-slash in the URL (such as
   "example//foo.html") should now return a 404 instead of a traceback and
   500 error (#3631)
 - downloadPage will now fire a Failure on its returned Deferred instead of
   indicating success when the connection is prematurely lost (#3645)
 - static.File will now provide a 404 instead of a 500 error when it was
   constructed with a non-existent file (#3634)
 - microdom should now serialize namespaces correctly (#3672)
 - The HTTP Auth support resource wrapper should no longer corrupt requests and
   cause them to skip a segment in the request path (#3679)
 - The twisted.web WSGI support should now include leading slashes in PATH_INFO,
   and SCRIPT_NAME will be empty if the application is at the root of the
   resource tree. This means that WSGI applications should no longer generate
   URLs with double-slashes in them even if they naively concatenate the values
   (#3721)
 - WSGI applications should now receive the requesting client's IP in the
   REMOTE_ADDR environment variable (#3730)
 - The distrib module should work again. It was unfortunately broken with the
   refactoring of twisted.web's header support (#3697)
 - static.File now supports multiple ranges specified in the Range header
   (#3574)
 - static.File should now generate a correct Content-Length value when the
   requested Range value doesn't fit entirely within the file's contents (#3814)
 - Attempting to call request.finish() after the connection has been lost will
   now immediately raise a RuntimeError (#4013)
 - An HTTP-auth resource should now be able to directly render the wrapped
   avatar, whereas before it would only allow retrieval of child resources
   (#4014)
 - twisted.web's wsgi support should no longer attempt to call request.finish
   twice, which would cause errors in certain cases (#4025)
 - WSGI applications should now be able to handle requests with large bodies
   (#4029)
 - Exceptions raised from WSGI applications should now more reliably be turned
   into 500 errors on the HTTP level (#4019)
 - DeferredResource now correctly passes through exceptions raised from the
   wrapped resource, instead of turning them all into 500 errors (#3932)
 - Agent.request now generates a Host header when no headers are passed at
   (#4131)

Deprecations and Removals
-------------------------
 - The unmaintained and untested twisted.web.monitor module was removed (#2763)
 - The twisted.web.woven package has been removed (#1522)
 - All of the error resources in twisted.web.error are now in
   twisted.web.resource, and accessing them through twisted.web.error is now
   deprecated (#3035)
 - To facilitate a simplification of the timeout logic in server.Session,
   various things have been deprecated (#3457)
   - the loopFactory attribute is now ignored
   - the checkExpired method now does nothing
   - the lifetime parameter to startCheckingExpiration is now ignored
 - The twisted.web.trp module is now deprecated (#2030)

Other
-----
 - #2763, #3540, #3575, #3610, #3605, #1176, #3539, #3750, #3761, #3779, #2677,
   #3782, #3904, #3919, #3418, #3990, #1404, #4050


Twisted Words 9.0.0 (2009-11-24)
================================

Features
--------
 - IRCClient.describe is a new method meant to replace IRCClient.me to send
   CTCP ACTION messages with less confusing behavior (#3910)
 - The XMPP client protocol implementation now supports ANONYMOUS SASL
   authentication (#4067)
 - The IRC client protocol implementation now has better support for the
   ISUPPORT server->client message, storing the data in a new
   ServerSupportedFeatures object accessible via IRCClient.supported (#3285)

Fixes
-----
 - The twisted.words IRC server now always sends an MOTD, which at least makes
   Pidgin able to successfully connect to a twisted.words IRC server (#2385)
 - The IRC client will now dispatch "RPL MOTD" messages received before a
   "RPL MOTD START" instead of raising an exception (#3676)
 - The IRC client protocol implementation no longer updates its 'nickname'
   attribute directly; instead, that attribute will be updated when the server
   acknowledges the change (#3377)
 - The IRC client protocol implementation now supports falling back to another
   nickname when a nick change request fails (#3377, #4010)

Deprecations and Removals
-------------------------
 - The TOC protocol implementation is now deprecated, since the protocol itself
   has been deprecated and obselete for quite a long time (#3580)
 - The gui "im" application has been removed, since it relied on GTK1, which is
   hard to find these days (#3699, #3340)

Other
-----
 - #2763, #3540, #3647, #3750, #3895, #3968, #4050


Core 8.2.0 (2008-12-16)
=======================

Features
--------
 - Reactors are slowly but surely becoming more isolated, thus improving
   testability (#3198)
 - FilePath has gained a realpath method, and FilePath.walk no longer infinitely
   recurses in the case of a symlink causing a self-recursing filesystem tree
   (#3098)
 - FilePath's moveTo and copyTo methods now have an option to disable following
   of symlinks (#3105)
 - Private APIs are now included in the API documentation (#3268)
 - hotshot is now the default profiler for the twistd --profile parameter and
   using cProfile is now documented (#3355, #3356)
 - Process protocols can now implement a processExited method, which is
   distinct from processEnded in that it is called immediately when the child
   has died, instead of waiting for all the file descriptors to be closed
   (#1291)
 - twistd now has a --umask option (#966, #3024)
 - A new deferToThreadPool function exists in twisted.internet.threads (#2845)
 - There is now an example of writing an FTP server in examples/ftpserver.py
   (#1579)
 - A new runAsEffectiveUser function has been added to twisted.python.util
   (#2607)
 - twisted.internet.utils.getProcessOutput now offers a mechanism for
   waiting for the process to actually end, in the event of data received on
   stderr (#3239)
 - A fullyQualifiedName function has been added to twisted.python.reflect
   (#3254)
 - strports now defaults to managing access to a UNIX socket with a lock;
   lockfile=0 can be included in the strports specifier to disable this
   behavior (#2295)
 - FTPClient now has a 'rename' method (#3335)
 - FTPClient now has a 'makeDirectory' method (#3500)
 - FTPClient now has a 'removeFile' method (#3491)
 - flushWarnings, A new Trial method for testing warnings, has been added
   (#3487, #3427, #3506)
 - The log observer can now be configured in .tac files (#3534)

Fixes
-----
 - TLS Session Tickets are now disabled by default, allowing connections to
   certain servers which hang when an empty session ticket is received (like
   GTalk) (#3463)
 - twisted.enterprise.adbapi.ConnectionPool's noisy attribute now defaults to
   False, as documented (#1806)
 - Error handling and logging in adbapi is now much improved (#3244)
 - TCP listeners can now be restarted (#2913)
 - Doctests can now be rerun with trial's --until-failure option (#2713)
 - Some memory leaks have been fixed in trial's --until-failure
   implementation (#3119, #3269)
 - Trial's summary reporter now prints correct runtime information and handles
   the case of 0 tests (#3184)
 - Trial and any other user of the 'namedAny' function now has better error
   reporting in the case of invalid module names (#3259)
 - Multiple instances of trial can now run in parallel in the same directory
   by creating _trial_temp directories with an incremental suffix (#2338)
 - Trial's failUnlessWarns method now works on Python 2.6 (#3223)
 - twisted.python.log now hooks into the warnings system in a way compatible
   with Python 2.6 (#3211)
 - The GTK2 reactor is now better supported on Windows, but still not passing
   the entire test suite (#3203)
 - low-level failure handling in spawnProcess has been improved and no longer
   leaks file descriptors (#2305, #1410)
 - Perspective Broker avatars now have their logout functions called in more
   cases (#392)
 - Log observers which raise exceptions are no longer removed (#1069)
 - transport.getPeer now always includes an IP address in the Address returned
   instead of a hostname (#3059)
 - Functions in twisted.internet.utils which spawn processes now avoid calling
   chdir in the case where no working directory is passed, to avoid some
   obscure permission errors (#3159)
 - twisted.spread.publish.Publishable no longer corrupts line endings on
   Windows (#2327)
 - SelectReactor now properly detects when a TLS/TCP connection has been
   disconnected (#3218)
 - twisted.python.lockfile no longer raises an EEXIST OSError and is much
   better supported on Windows (#3367)
 - When ITLSTransport.startTLS is called while there is data in the write
   buffer, TLS negotiation will now be delayed instead of the method raising
   an exception (#686)
 - The userAnonymous argument to FTPFactory is now honored (#3390)
 - twisted.python.modules no longer tries to "fix" sys.modules after an import
   error, which was just causing problems (#3388)
 - setup.py no longer attempts to build extension modules when run with Jython
   (#3410)
 - AMP boxes can now be sent in IBoxReceiver.startReceivingBoxes (#3477)
 - AMP connections are closed as soon as a key length larger than 255 is
   received (#3478)
 - Log events with timezone offsets between -1 and -59 minutes are now
   correctly reported as negative (#3515)

Deprecations and Removals
-------------------------
 - Trial's setUpClass and tearDownClass methods are now deprecated (#2903)
 - problemsFromTransport has been removed in favor of the argument passed to
   connectionLost (#2874)
 - The mode parameter to methods of IReactorUNIX and IReactorUNIXDatagram are
   deprecated in favor of applications taking other security precautions, since
   the mode of a Unix socket is often not respected (#1068)
 - Index access on instances of twisted.internet.defer.FirstError has been
   removed in favor of the subFailure attribute (#3298)
 - The 'changeDirectory' method of FTPClient has been deprecated in favor of
   the 'cwd' method (#3491)

Other
-----

 - #3202, #2869, #3225, #2955, #3237, #3196, #2355, #2881, #3054, #2374, #2918,
   #3210, #3052, #3267, #3288, #2985, #3295, #3297, #2512, #3302, #1222, #2631,
   #3306, #3116, #3215, #1489, #3319, #3320, #3321, #1255, #2169, #3182, #3323,
   #3301, #3318, #3029, #3338, #3346, #1144, #3173, #3165, #685, #3357, #2582,
   #3370, #2438, #1253, #637, #1971, #2208, #979, #1790, #1888, #1882, #1793,
   #754, #1890, #1931, #1246, #1025, #3177, #2496, #2567, #3400, #2213, #2027,
   #3415, #1262, #3422, #2500, #3414, #3045, #3111, #2974, #2947, #3222, #2878,
   #3402, #2909, #3423, #1328, #1852, #3382, #3393, #2029, #3489, #1853, #2026,
   #2375, #3502, #3482, #3504, #3505, #3507, #2605, #3519, #3520, #3121, #3484,
   #3439, #3216, #3511, #3524, #3521, #3197, #2486, #2449, #2748, #3381, #3236,
   #671


Conch 8.2.0 (2008-12-16)
========================

Features
--------
 - The type of the protocols instantiated by SSHFactory is now parameterized
   (#3443)

Fixes
-----
 - A file descriptor leak has been fixed (#3213, #1789)
 - "File Already Exists" errors are now handled more correctly (#3033)
 - Handling of CR IAC in TelnetClient is now improved (#3305)
 - SSHAgent is no longer completely unusable (#3332)
 - The performance of insults.ClientProtocol is now greatly increased by
   delivering more than one byte at a time to application code (#3386)
 - Manhole and the conch server no longer need to be run as root when not
   necessary (#2607)
 - The value of FILEXFER_ATTR_ACMODTIME has been corrected (#2902)
 - The management of known_hosts and host key verification has been overhauled
   (#1376, #1301, #3494, #3496, #1292, #3499)

Other
-----
 - #3193, #1633


Lore 8.2.0 (2008-12-16)
=======================

Other
-----
 - #2207, #2514


Mail 8.2.0 (2008-12-16)
=======================

Fixes
-----
 - The mailmail tool now provides better error messages for usage errors (#3339)
 - The SMTP protocol implementation now works on PyPy (#2976)

Other
-----
 - #3475


Names 8.2.0 (2008-12-16)
========================

Features
--------
 - The NAPTR record type is now supported (#2276)

Fixes
-----
 - Make client.Resolver less vulnerable to the Birthday Paradox attack by
   avoiding sending duplicate queries when it's not necessary (#3347)
 - client.Resolver now uses a random source port for each DNS request (#3342)
 - client.Resolver now uses a full 16 bits of randomness for message IDs,
   instead of 10 which it previously used (#3342)
 - All record types now have value-based equality and a string representation
   (#2935)

Other
-----
 - #1622, #3424


Web 8.2.0 (2008-12-16)
======================

Features
--------
 - The web server can now deal with multi-value headers in the new attributes of
   Request, requestHeaders and responseHeaders (#165)
 - There is now a resource-wrapper which implements HTTP Basic and Digest auth
   in terms of twisted.cred (#696)
 - It's now possible to limit the number of redirects that client.getPage will
   follow (#2412)
 - The directory-listing code no longer uses Woven (#3257)
 - static.File now supports Range headers with a single range (#1493)
 - twisted.web now has a rudimentary WSGI container (#2753)
 - The web server now supports chunked encoding in requests (#3385)

Fixes
-----
 - The xmlrpc client now raises an error when the server sends an empty
   response (#3399)
 - HTTPPageGetter no longer duplicates default headers when they're explicitly
   overridden in the headers parameter (#1382)
 - The server will no longer timeout clients which are still sending request
   data (#1903)
 - microdom's isEqualToNode now returns False when the nodes aren't equal
   (#2542)

Deprecations and Removals
-------------------------

 - Request.headers and Request.received_headers are not quite deprecated, but
   they are discouraged in favor of requestHeaders and responseHeaders (#165)

Other
-----
 - #909, #687, #2938, #1152, #2930, #2025, #2683, #3471


Web2 8.2.0 (2008-12-16)
=======================

Note: Twisted Web2 is being phased out in preference for Twisted Web, but some
maintenance changes have been made.

Fixes
-----
 - The main twisted.web2 docstring now indicates the current state of the
   project (#2028)
 - Headers which require unusual bytes are now quoted (#2346)
 - Some links in the introduction documentation have been fixed (#2552)


Words 8.2.0 (2008-12-16)
========================

Feature
-------
 - There is now a standalone XMPP router included in twisted.words: it can be
   used with the 'twistd xmpp-router' command line (#3407)
 - A server factory for Jabber XML Streams has been added (#3435)
 - Domish now allows for iterating child elements with specific qualified names
   (#2429)
 - IRCClient now has a 'back' method which removes the away status (#3366)
 - IRCClient now has a 'whois' method (#3133)

Fixes
-----
 - The IRC Client implementation can now deal with compound mode changes (#3230)
 - The MSN protocol implementation no longer requires the CVR0 protocol to
   be included in the VER command (#3394)
 - In the IRC server implementation, topic messages will no longer be sent for
   a group which has no topic (#2204)
 - An infinite loop (which caused infinite memory usage) in irc.split has been
   fixed.  This was triggered any time a message that starts with a delimiter
   was sent (#3446)
 - Jabber's toResponse now generates a valid stanza even when stanzaType is not
   specified (#3467)
 - The lifetime of authenticator instances in XmlStreamServerFactory is no
   longer artificially extended (#3464)

Other
-----
 - #3365


Core 8.1.0 (2008-05-18)
=======================

Features
--------

 - twisted.internet.error.ConnectionClosed is a new exception which is the
   superclass of ConnectionLost and ConnectionDone (#3137)
 - Trial's CPU and memory performance should be better now (#3034)
 - twisted.python.filepath.FilePath now has a chmod method (#3124)

Fixes
-----

 - Some reactor re-entrancy regressions were fixed (#3146, #3168)
 - A regression was fixed whereby constructing a Failure for an exception and
   traceback raised out of a Pyrex extension would fail (#3132)
 - CopyableFailures in PB can again be created from CopiedFailures (#3174)
 - FilePath.remove, when called on a FilePath representing a symlink to a
   directory, no longer removes the contents of the targeted directory, and
   instead removes the symlink (#3097)
 - FilePath now has a linkTo method for creating new symlinks (#3122)
 - The docstring for Trial's addCleanup method now correctly specifies when
   cleanup functions are run (#3131)
 - assertWarns now deals better with multiple identical warnings (#2904)
 - Various windows installer bugs were fixed (#3115, #3144, #3150, #3151, #3164)
 - API links in the howto documentation have been corrected (#3130)
 - The Win32 Process transport object now has a pid attribute (#1836)
 - A doc bug in the twistd plugin howto which would inevitably lead to
   confusion was fixed (#3183)
 - A regression breaking IOCP introduced after the last release was fixed
   (#3200)

Deprecations and Removals
-------------------------

 - mktap is now fully deprecated, and will emit DeprecationWarnings when used
   (#3127)

Other
-----
 - #3079, #3118, #3120, #3145, #3069, #3149, #3186, #3208, #2762


Conch 8.1.0 (2008-05-18)
========================

Fixes
-----
 - A regression was fixed whereby the publicKeys and privateKeys attributes of
   SSHFactory would not be interpreted as strings (#3141)
 - The sshsimpleserver.py example had a minor bug fix (#3135)
 - The deprecated mktap API is no longer used (#3127)
 - An infelicity was fixed whereby a NameError would be raised in certain
   circumstances during authentication when a ConchError should have been
   (#3154)
 - A workaround was added to conch.insults for a bug in gnome-terminal whereby
   it would not scroll correctly (#3189)


Lore 8.1.0 (2008-05-18)
=======================

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)


News 8.1.0 (2008-05-18)
=======================

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)


Web 8.1.0 (2008-05-18)
======================

Fixes
-----
 - Fixed an XMLRPC bug whereby sometimes a callRemote Deferred would
   accidentally be fired twice when a connection was lost during the handling of
   a response (#3152)
 - Fixed a bug in the "Using Twisted Web" document which prevented an example
   resource from being renderable (#3147)
 - The deprecated mktap API is no longer used (#3127)


Words 8.1.0 (2008-05-18)
========================

Features
--------
 - JID objects now have a nice __repr__ (#3156)
 - Extending XMPP protocols is now easier (#2178)

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)
 - A bug whereby one-time XMPP observers would be enabled permanently was fixed
   (#3066)


Mail 8.1.0 (2008-05-18)
=======================

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)


Names 8.1.0 (2008-05-18)
========================

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)


Web2 8.1.0 (2008-05-18)
=======================

Fixes
-----
 - The deprecated mktap API is no longer used (#3127)


Core 8.0.1 (2008-03-26)
=======================

Fixes
-----
 - README no longer refers to obsolete trial command line option
 - twistd no longer causes a bizarre DeprecationWarning about mktap


Core 8.0.0 (2008-03-17)
=======================

Features
--------

 - The IOCP reactor has had many changes and is now greatly improved
   (#1760, #3055)
 - The main Twisted distribution is now easy_installable (#1286, #3110)
 - twistd can now profile with cProfile (#2469)
 - twisted.internet.defer contains a DeferredFilesystemLock which gives a
   Deferred interface to lock file acquisition (#2180)
 - twisted.python.modules is a new system for representing and manipulating
   module paths (i.e. sys.path) (#1951)
 - twisted.internet.fdesc now contains a writeToFD function, along with other
   minor fixes (#2419)
 - twisted.python.usage now allows optional type enforcement (#739)
 - The reactor now has a blockingCallFromThread method for non-reactor threads
   to use to wait for a reactor-scheduled call to return a result (#1042, #3030)
 - Exceptions raised inside of inlineCallbacks-using functions now have a
   better chance of coming with a meaningful traceback (#2639, #2803)
 - twisted.python.randbytes now contains code for generating secure random
   bytes (#2685)
 - The classes in twisted.application.internet now accept a reactor parameter
   for specifying the reactor to use for underlying calls to allow for better
   testability (#2937)
 - LoopingCall now allows you to specify the reactor to use to schedule new
   calls, allowing much better testing techniques (#2633, #2634)
 - twisted.internet.task.deferLater is a new API for scheduling calls and
   getting deferreds which are fired with their results (#1875)
 - objgrep now knows how to search through deque objects (#2323)
 - twisted.python.log now contains a Twisted log observer which can forward
   messages to the Python logging system (#1351)
 - Log files now include seconds in the timestamps (#867)
 - It is now possible to limit the number of log files to create during log
   rotation (#1095)
 - The interface required by the log context system is now documented as
   ILoggingContext, and abstract.FileDescriptor now declares that it implements
   it (#1272)
 - There is now an example cred checker that uses a database via adbapi (#460)
 - The epoll reactor is now documented in the choosing-reactors howto (#2539)
 - There were improvements to the client howto (#222)
 - Int8Receiver was added (#2315)
 - Various refactorings to AMP introduced better testability and public
   interfaces (#2657, #2667, #2656, #2664, #2810)
 - twisted.protocol.policies.TrafficLoggingFactory now has a resetCounter
   method (#2757)
 - The FTP client can be told which port range within which to bind passive
   transfer ports (#1904)
 - twisted.protocols.memcache contains a new asynchronous memcache client
   (#2506, #2957)
 - PB now supports anonymous login (#439, #2312)
 - twisted.spread.jelly now supports decimal objects (#2920)
 - twisted.spread.jelly now supports all forms of sets (#2958)
 - There is now an interface describing the API that process protocols must
   provide (#3020)
 - Trial reporting to core unittest TestResult objects has been improved (#2495)
 - Trial's TestCase now has an addCleanup method which allows easy setup of
   tear-down code (#2610, #2899)
 - Trial's TestCase now has an assertIsInstance method (#2749)
 - Trial's memory footprint and speed are greatly improved (#2275)
 - At the end of trial runs, "PASSED" and "FAILED" messages are now colorized
   (#2856)
 - Tests which leave global state around in the reactor will now fail in
   trial. A new option, --unclean-warnings, will convert these errors back into
   warnings (#2091)
 - Trial now has a --without-module command line for testing code in an
   environment that lacks a particular Python module (#1795)
 - Error reporting of failed assertEquals assertions now has much nicer
   formatting (#2893)
 - Trial now has methods for monkey-patching (#2598)
 - Trial now has an ITestCase (#2898, #1950)
 - The trial reporter API now has a 'done' method which is called at the end of
   a test run (#2883)
 - TestCase now has an assertWarns method which allows testing that functions
   emit warnings (#2626, #2703)
 - There are now no string exceptions in the entire Twisted code base (#2063)
 - There is now a system for specifying credentials checkers with a string
   (#2570)

Fixes
-----

 - Some tests which were asserting the value of stderr have been changed
   because Python uncontrollably writes bytes to stderr (#2405)
 - Log files handle time zones with DST better (#2404)
 - Subprocesses using PTYs on OS X that are handled by Twisted will now be able
   to more reliably write the final bytes before they exit, allowing Twisted
   code to more reliably receive them (#2371, #2858)
 - Trial unit test reporting has been improved (#1901)
 - The kqueue reactor handles connection failures better (#2172)
 - It's now possible to run "trial foo/bar/" without an exception: trailing
   slashes no longer cause problems (#2005)
 - cred portals now better deal with implementations of inherited interfaces
   (#2523)
 - FTP error handling has been improved (#1160, 1107)
 - Trial behaves better with respect to file locking on Windows (#2482)
 - The FTP server now gives a better error when STOR is attempted during an
   anonymous session (#1575)
 - Trial now behaves better with tests that use the reactor's threadpool (#1832)
 - twisted.python.reload now behaves better with new-style objects (#2297)
 - LogFile's defaultMode parameter is now better implemented, preventing
   potential security exploits (#2586)
 - A minor obscure leak in thread pools was corrected (#1134)
 - twisted.internet.task.Clock now returns the correct DelayedCall from
   callLater, instead of returning the one scheduled for the furthest in the
   future (#2691)
 - twisted.spread.util.FilePager no longer unnecessarily buffers data in
   memory (#1843, 2321)
 - Asking for twistd or trial to use an unavailable reactor no longer prints a
   traceback (#2457)
 - System event triggers have fewer obscure bugs (#2509)
 - Plugin discovery code is much better behaved, allowing multiple
   installations of a package with plugins (#2339, #2769)
 - Process and PTYProcess have been merged and some minor bugs have been fixed
   (#2341)
 - The reactor has less global state (#2545)
 - Failure can now correctly represent and format errors caused by string
   exceptions (#2830)
 - The epoll reactor now has better error handling which now avoids the bug
   causing 100% CPU usage in some cases (#2809)
 - Errors raised during trial setUp or tearDown methods are now handled better
   (#2837)
 - A problem when deferred callbacks add new callbacks to the deferred that
   they are a callback of was fixed (#2849)
 - Log messages that are emitted during connectionMade now have the protocol
   prefix correctly set (#2813)
 - The string representation of a TCP Server connection now contains the actual
   port that it's bound to when it was configured to listen on port 0 (#2826)
 - There is better reporting of error codes for TCP failures on Windows (#2425)
 - Process spawning has been made slightly more robust by disabling garbage
   collection temporarily immediately after forking so that finalizers cannot
   be executed in an unexpected environment (#2483)
 - namedAny now detects import errors better (#698)
 - Many fixes and improvements to the twisted.python.zipstream module have
   been made (#2996)
 - FilePager no longer blows up on empty files (#3023)
 - twisted.python.util.FancyEqMixin has been improved to cooperate with objects
   of other types (#2944)
 - twisted.python.FilePath.exists now restats to prevent incorrect result
   (#2896)
 - twisted.python.util.mergeFunctionMetadata now also merges the __module__
   attribute (#3049)
 - It is now possible to call transport.pauseProducing within connectionMade on
   TCP transports without it being ignored (#1780)
 - twisted.python.versions now understands new SVN metadata format for fetching
   the SVN revision number (#3058)
 - It's now possible to use reactor.callWhenRunning(reactor.stop) on gtk2 and
   glib2 reactors (#3011)

Deprecations and removals
-------------------------
 - twisted.python.timeoutqueue is now deprecated (#2536)
 - twisted.enterprise.row and twisted.enterprise.reflector are now deprecated
   (#2387)
 - twisted.enterprise.util is now deprecated (#3022)
 - The dispatch and dispatchWithCallback methods of ThreadPool are now
   deprecated (#2684)
 - Starting the same reactor multiple times is now deprecated (#1785)
 - The visit method of various test classes in trial has been deprecated (#2897)
 - The --report-profile option to twistd and twisted.python.dxprofile are
   deprecated (#2908)
 - The upDownError method of Trial reporters is deprecated (#2883)

Other
-----

 - #2396, #2211, #1921, #2378, #2247, #1603, #2463, #2530, #2426, #2356, #2574,
 - #1844, #2575, #2655, #2640, #2670, #2688, #2543, #2743, #2744, #2745, #2746,
 - #2742, #2741, #1730, #2831, #2216, #1192, #2848, #2767, #1220, #2727, #2643,
 - #2669, #2866, #2867, #1879, #2766, #2855, #2547, #2857, #2862, #1264, #2735,
 - #942, #2885, #2739, #2901, #2928, #2954, #2906, #2925, #2942, #2894, #2793,
 - #2761, #2977, #2968, #2895, #3000, #2990, #2919, #2969, #2921, #3005, #421,
 - #3031, #2940, #1181, #2783, #1049, #3053, #2847, #2941, #2876, #2886, #3086,
 - #3095, #3109


Conch 8.0.0 (2008-03-17)
========================

Features
--------
 - Add DEC private mode manipulation methods to ITerminalTransport. (#2403)

Fixes
-----
 - Parameterize the scheduler function used by the insults TopWindow widget.
   This change breaks backwards compatibility in the TopWindow initializer.
   (#2413)
 - Notify subsystems, like SFTP, of connection close. (#2421)
 - Change the process file descriptor "connection lost" code to reverse the
   setNonBlocking operation done during initialization. (#2371)
 - Change ConsoleManhole to wait for connectionLost notification before
   stopping the reactor. (#2123, #2371)
 - Make SSHUserAuthServer.ssh_USERAUTH_REQUEST return a Deferred. (#2528)
 - Manhole's initializer calls its parent class's initializer with its
   namespace argument. (#2587)
 - Handle ^C during input line continuation in manhole by updating the prompt
   and line buffer correctly. (#2663)
 - Make twisted.conch.telnet.Telnet by default reject all attempts to enable
   options. (#1967)
 - Reduce the number of calls into application code to deliver application-level
   data in twisted.conch.telnet.Telnet.dataReceived (#2107)
 - Fix definition and management of extended attributes in conch file transfer.
   (#3010)
 - Fix parsing of OpenSSH-generated RSA keys with differing ASN.1 packing style.
   (#3008)
 - Fix handling of missing $HOME in twisted.conch.client.unix. (#3061)

Misc
----
 - #2267, #2378, #2604, #2707, #2341, #2685, #2679, #2912, #2977, #2678, #2709
   #2063, #2847


Lore 8.0.0 (2008-03-17)
=======================

Fixes
-----
 - Change twisted.lore.tree.setIndexLin so that it removes node with index-link
   class when the specified index filename is None. (#812)
 - Fix the conversion of the list of options in man pages to Lore format.
   (#3017)
 - Fix conch man pages generation. (#3075)
 - Fix management of the interactive command tag in man2lore. (#3076)

Misc
----
 - #2847


News 8.0.0 (2008-03-17)
=======================

Misc
----
 - Remove all "API Stability" markers (#2847)


Runner 8.0.0 (2008-03-17)
=========================

Misc
----
 - Remove all "API Stability" markers (#2847)


Web 8.0.0 (2008-03-17)
======================

Features
--------
 - Add support to twisted.web.client.getPage for the HTTP HEAD method. (#2750)

Fixes
-----
 - Set content-type in xmlrpc responses to "text/xml" (#2430)
 - Add more error checking in the xmlrpc.XMLRPC render method, and enforce
   POST requests. (#2505)
 - Reject unicode input to twisted.web.client._parse to reject invalid
   unicode URLs early. (#2628)
 - Correctly re-quote URL path segments when generating an URL string to
   return from Request.prePathURL. (#2934)
 - Make twisted.web.proxy.ProxyClientFactory close the connection when
   reporting a 501 error. (#1089)
 - Fix twisted.web.proxy.ReverseProxyResource to specify the port in the
   host header if different from 80. (#1117)
 - Change twisted.web.proxy.ReverseProxyResource so that it correctly encodes
   the request URI it sends on to the server for which it is a proxy. (#3013)
 - Make "twistd web --personal" use PBServerFactory (#2681)

Misc
----
 - #1996, #2382, #2211, #2633, #2634, #2640, #2752, #238, #2905


Words 8.0.0 (2008-03-17)
========================

Features
--------
 - Provide function for creating XMPP response stanzas. (#2614, #2614)
 - Log exceptions raised in Xish observers. (#2616)
 - Add 'and' and 'or' operators for Xish XPath expressions. (#2502)
 - Make JIDs hashable. (#2770)

Fixes
-----
 - Respect the hostname and servername parameters to IRCClient.register. (#1649)
 - Make EventDispatcher remove empty callback lists. (#1652)
 - Use legacy base64 API to support Python 2.3 (#2461)
 - Fix support of DIGEST-MD5 challenge parsing with multi-valued directives.
   (#2606)
 - Fix reuse of dict of prefixes in domish.Element.toXml (#2609)
 - Properly process XMPP stream headers (#2615)
 - Use proper namespace for XMPP stream errors. (#2630)
 - Properly parse XMPP stream errors. (#2771)
 - Fix toResponse for XMPP stanzas without an id attribute. (#2773)
 - Move XMPP stream header procesing to authenticators. (#2772)

Misc
----
 - #2617, #2640, #2741, #2063, #2570, #2847


Mail 8.0.0 (2008-03-17)
=======================

Features
--------
 - Support CAPABILITY responses that include atoms of the form "FOO" and
   "FOO=BAR" in IMAP4 (#2695)
 - Parameterize error handling behavior of imap4.encoder and imap4.decoder.
   (#2929)

Fixes
-----
 - Handle empty passwords in SMTP auth. (#2521)
 - Fix IMAP4Client's parsing of literals which are not preceded by whitespace.
   (#2700)
 - Handle MX lookup succeeding without answers. (#2807)
 - Fix issues with aliases(5) process support. (#2729)

Misc
----
 - #2371, #2123, #2378, #739, #2640, #2746, #1917, #2266, #2864, #2832, #2063,
   #2865, #2847


Names 8.0.0 (2008-03-17)
========================

Fixes
-----

 - Refactor DNSDatagramProtocol and DNSProtocol to use same base class (#2414)
 - Change Resolver to query specified nameservers in specified order, instead
   of reverse order. (#2290)
 - Make SRVConnector work with bad results and NXDOMAIN responses.
   (#1908, #2777)
 - Handle write errors happening in dns queries, to have correct deferred
   failures. (#2492)
 - Fix the value of OP_NOTIFY and add a definition for OP_UPDATE. (#2945)

Misc
----
 - #2685, #2936, #2581, #2847
