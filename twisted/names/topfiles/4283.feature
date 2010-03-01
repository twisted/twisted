twisted.names.dns.Message now uses a specially constructed dictionary for looking up record types.  This yields a significant performance improvement on PyPy.
