class Maildir(pb.Referencable):

    def __init__(self, directory, rootDirectory):
        self.virtualDirectory = directory 
        self.rootDirectory = rootDirectory 
        self.directory = os.path.join(rootDirectory, directory)

    def getFolderMessage(self, folder, name):
        if '/' in name:
            raise IOError("can only open files in '%s' directory'" % folder)
        fp = open(os.path.join(self.directory, 'new', name)
        try:
            return fp.read()
        finally:
            fp.close() 

    def deleteFolderMessage(self, folder, name):
        if '/' in name:
            raise IOError("can only delete files in '%s' directory'" % folder)
        os.rename(os.path.join(self.directory, folder, name),
                  os.path.join(self.rootDirectory, '.Trash', folder, name))

    def deleteNewMessage(self, name):
        return self.deleteFolderMessage('new', name)
    remote_deleteNewMessage = deleteNewMessage

    def deleteCurMessage(self, name):
        return self.deleteFolderMessage('cur', name)
    remote_deleteCurMessage = deleteCurMessage

    def getNewMessages(self):
        return os.listdir(os.path.join(self.directory, 'new'))
    remote_getNewMessages = getNewMessages

    def getCurMessages(self):
        return os.listdir(os.path.join(self.directory, 'cur'))
    remote_getCurMessages = getCurMessages

    def getNewMessage(self, name): 
        return self.getFolderMessage('new', name)
    remote_getNewMessage = getNewMessage

    def getCurMessage(self, name): 
        return self.getFolderMessage('cur', name)
    remote_getCurMessage = getCurMessage

    def getSubFolder(self, name):
        if name[0] == '.':
            raise IOError("subfolder name cannot begin with a '.'")
        name = string.replace(name, '/', ':')
        if self.virtualDirectoy == '.':
            name = '.'+name
        else:
            name = self.virtualDirectory+':'+name
        if not self._isSubFolder(name):
            raise IOError("not a subfolder")
        return Maildir(name, self.rootDirectory)
    remote_getSubFolder = getSubFolder

    def _isSubFolder(self, name):
        return (not os.path.isdir(os.path.join(self.rootDirectory, name)) or
                not os.path.isfile(os.path.join(self.rootDirectory, name, 
                                                'maildirfolder'))
