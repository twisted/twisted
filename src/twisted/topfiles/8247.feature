twisted.internet.ssl.CertificateOptions now sets the OpenSSL context's mode to MODE_RELEASE_BUFFERS, which will free the read/write buffers on idle TLS connections to save memory.
