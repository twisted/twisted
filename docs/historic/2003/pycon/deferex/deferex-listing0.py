
class DocumentProcessor:
    def __init__(self):
        self.loadDocuments(self.callback, mySrv, "hello")

    def loadDocuments(callback, server, keyword):
        "Retrieve a set of documents!"
        ...

    def callback(self, documents):
        try:
            for document in documents:
                process(document)
        finally:
            self.cleanup()

    def cleanup(self):
        ...
