twisted.protocols.ftp.FTPRealm now accepts a parameter to override "/home"
as the container for user directories.  The new BaseFTPRealm class in the
same module also allows easy implementation of custom user directory
schemes.
