from twisted.python.components import Interface

class IConchUser(Interface):
    """A user who has been authenticated to Cred through Conch.  This is 
    the interface between the SSH connection and the user.

    @ivar conn: The SSHConnection object for this user.
    """

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        """
        The other side requested a channel of some sort.
        channelType is the type of channel being requested,
        windowSize is the initial size of the remote window,
        maxPacket is the largest packet we should send,
        data is any other packet data (often nothing).

        We return a subclass of SSHChannel.  If an appropriate
        channel can not be found, an exception will be raised.
        If a ConchError is raised, the .value will be the message,
        and the .data will be the error code.

        @type channelType:  C{str}
        @type windowSize:   C{int}
        @type maxPacket:    C{int}
        @type data:         C{str}
        @rtype:             subclass of C{SSHChannel}/C{tuple}
        """

    def lookupSubsystem(self, subsystem, data):
        """
        The other side requested a subsystem.
        subsystem is the name of the subsystem being requested.
        data is any other packet data (often nothing).
        
        We return a Protocol.
        """

    def gotGlobalRequest(self, requestType, data):
        """
        A global request was sent from the other side.
        
        By default, this dispatches to a method 'channel_channelType' with any
        non-alphanumerics in the channelType replace with _'s.  If it cannot 
        find a suitable method, it returns an OPEN_UNKNOWN_CHANNEL_TYPE error. 
        The method is called with arguments of windowSize, maxPacket, data.
        """

class ISession(Interface):

    def getPty(self, term, windowSize, modes):
        """
        Get a psuedo-terminal for use by a shell or command.

        If a psuedo-terminal is not available, or the request otherwise
        fails, raise an exception.
        """

    def openShell(self, proto):
        """
        Open a shell and connect it to proto.

        proto should be a ProcessProtocol instance.
        """

    def execCommand(self, proto, command):
        """
        Execute a command.

        proto should be a ProcessProtocol instance.
        """

    def windowChanged(self, newWindowSize):
        """
        Called when the size of the remote screen has changed.
        """

    def closed(self):
        """
        Called when the session is closed.
        """


class ISFTPServer(Interface):
    """
    The only attribute of this class is "avatar".  It is the avatar
    returned by the Realm that we are authenticated with, and
    represents the logged-in user.  Each method should check to verify
    that the user has permission for their actions.
    """

    def gotVersion(self, otherVersion, extData):
        """
        Called when the client sends their version info.

        otherVersion is an integer representing the version of the SFTP
        protocol they are claiming.
        extData is a dictionary of extended_name : extended_data items.
        These items are sent by the client to indicate additional features.

        This method should return a dictionary of extended_name : extended_data
        items.  These items are the additional features (if any) supported
        by the server.
        """
        return {}

    def openFile(self, filename, flags, attrs):
        """
        Called when the clients asks to open a file.

        filename is a string representing the file to open.

        flags is a integer of the flags to open the file with, ORed together.
        The flags and their values are listed at the bottom of this file.

        attrs is a list of attributes to open the file with.  It is a
        dictionary, consisting of 0 or more keys.  The possible keys are:
            size: the size of the file in bytes
            uid: the user ID of the file as an integer
            gid: the group ID of the file as an integer
            permissions: the permissions of the file with as an integer.
            the bit representation of this field is defined by POSIX.
            atime: the access time of the file as seconds since the epoch.
            mtime: the modification time of the file as seconds since the epoch.
            ext_*: extended attributes.  The server is not required to
            understand this, but it may.

        NOTE: there is no way to indicate text or binary files.  it is up
        to the SFTP client to deal with this.

        This method returns an object that meets the ISFTPFile interface.
        Alternatively, it can return a Deferred that will be called back
        with the object.
        """

    def removeFile(self, filename):
        """
        Remove the given file.

        filename is the name of the file as a string.

        This method returns when the remove succeeds, or a Deferred that is
        called back when it succeeds.
        """

    def renameFile(self, oldpath, newpath):
        """
        Rename the given file.

        oldpath is the current location of the file.
        newpath is the new file name.

        This method returns when the rename succeeds, or a Deferred that is
        called back when it succeeds.
        """

    def makeDirectory(self, path, attrs):
        """
        Make a directory.

        path is the name of the directory to create as a string.
        attrs is a dictionary of attributes to create the directory with.
        It's meaning is the same as the attrs in the openFile method.

        This method returns when the directory is created, or a Deferred that
        is called back when it is created.
        """

    def removeDirectory(self, path):
        """
        Remove a directory (non-recursively)

        path is the directory to remove.

        It is an error to remove a directory that has files or directories in
        it.

        This method returns when the directory is removed, or a Deferred that
        is called back when it is removed.
        """

    def openDirectory(self, path):
        """
        Open a directory for scanning.

        path is the directory to open.

        This method returns an iterable object that has a close() method,
        or a Deferred that is called back with same.

        The close() method is called when the client is finished reading
        from the directory.  At this point, the iterable will no longer
        be used.

        The iterable should return triples of the form (filename,
        longname, attrs) or Deferreds that return the same.  The
        sequence must support __getitem__, but otherwise may be any
        'sequence-like' object.

        filename is the name of the file relative to the directory.
        logname is an expanded format of the filename.  The recommended format
        is:
        -rwxr-xr-x   1 mjos     staff      348911 Mar 25 14:29 t-filexfer
        1234567890 123 12345678 12345678 12345678 123456789012

        The first line is sample output, the second is the length of the field.
        The fields are: permissions, link count, user owner, group owner,
        size in bytes, modification time.

        attrs is a dictionary in the format of the attrs argument to openFile.
        """

    def getAttrs(self, path, followLinks):
        """
        Return the attributes for the given path.

        path is the path to return attributes for as a string.
        followLinks is a boolean.  if it is True, follow symbolic links
        and return attributes for the real path at the base.  if it is False,
        return attributes for the specified path.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.
        """

    def setAttrs(self, path, attrs):
        """
        Set the attributes for the path.

        path is the path to set attributes for as a string.
        attrs is a idctionary in the same format as the attrs argument to
        openFile.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.
        """

    def readLink(self, path):
        """
        Find the root of a set of symbolic links.

        path is the path of the symlink to read.

        This method returns the target of the link, or a Deferred that
        returns the same.
        """

    def makeLink(self, linkPath, targetPath):
        """
        Create a symbolic link.

        linkPath is is the pathname of the symlink as a string
        targetPath is the path of the target of the link as a string.

        This method returns when the link is made, or a Deferred that
        returns the same.
        """

    def realPath(self, path):
        """
        Convert any path to an absolute path.

        path is the path to convert as a string.

        This method returns the absolute path as a string, or a Deferred
        that returns the same.
        """

class ISFTPFile:
    """
    This represents an open file on the server.  An object adhering to this
    interface should be returned from openFile().
    """

    def close(self):
        """
        Close the file.

        This method returns nothing if the close succeeds immediatly, or a
        Deferred that is called back when the close succeeds.
        """

    def readChunk(self, offset, length):
        """
        Read from the file.

        offset is an integer that is the index to start from in the file.
        length is the maximum length of data to return.  The actual amount
        returned may less than this.  For normal disk files, however,
        this should read the requested number (up to the end of the file).

        If EOF is reached before any data is read, raise EOFError.

        This method returns the data as a string, or a Deferred that is
        called back with same.
        """

    def writeChunk(self, offset, data):
        """
        Write to the file.

        offset is an integer that is the index to start from in the file.
        data is a string that is the data to write.

        This method returns when the write completes, or a Deferred that is
        called when it completes.
        """

    def getAttrs(self):
        """
        Return the attributes for the file.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.
        """

    def setAttrs(self, attrs):
        """
        Set the attributes for the file.

        attrs is a dictionary in the same format as the attrs argument to
        openFile.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.
        """

class ISFTPFile:
    """
    This represents an open file on the server.  An object adhering to this
    interface should be returned from openFile().
    """

    def close(self):
        """
        Close the file.

        This method returns nothing if the close succeeds immediatly, or a
        Deferred that is called back when the close succeeds.
        """

    def readChunk(self, offset, length):
        """
        Read from the file.

        offset is an integer that is the index to start from in the file.
        length is the maximum length of data to return.  The actual amount
        returned may less than this.  For normal disk files, however,
        this should read the requested number (up to the end of the file).

        If EOF is reached before any data is read, raise EOFError.

        This method returns the data as a string, or a Deferred that is
        called back with same.
        """

    def writeChunk(self, offset, data):
        """
        Write to the file.

        offset is an integer that is the index to start from in the file.
        data is a string that is the data to write.

        This method returns when the write completes, or a Deferred that is
        called when it completes.
        """

    def getAttrs(self):
        """
        Return the attributes for the file.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.
        """

    def setAttrs(self, attrs):
        """
        Set the attributes for the file.

        attrs is a dictionary in the same format as the attrs argument to
        openFile.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.
        """

