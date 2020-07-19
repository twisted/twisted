The enableSessions argument to twisted.internet.ssl.CertificateOptions now
actually enables/disables OpenSSL's session cache.  Also, due to
session-related bugs, it defaults to False.