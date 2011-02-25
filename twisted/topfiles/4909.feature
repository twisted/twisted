twisted.protocols.ftp.FTP.ftp_STOR now catches `FTPCmdError`s raised by
the file writer, and returns the error back to the client.
