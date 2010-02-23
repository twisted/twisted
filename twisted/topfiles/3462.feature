twisted.protocol.ftp.IWriteFile now has a close() method, which can return a
Deferred. Previously a STOR command would finish immediately upon the receipt
of the last byte of the uploaded file. With close(), the backend can delay
the finish until it has performed some other slow action (like storing the
data to a virtual filesystem).
