class BookmarkContainer(object):
    _page_url = None
    _category = None
    def __init__(self, bookmarks=[]):
        self.bookmarks = bookmarks
        self.id_dict = {}
        self.TRACE = False
    
    def __len__(self):
        return len(self.bookmarks)

    def __getitem__(self, key):
        return self.bookmarks[key]

    def __setitem__(self, key, value):
        self.bookmarks[key] = value
        self._reindex()
    
    def __delitem__(self, key):
        self.bookmarks.remove(key)

    def __contains__(self, item):
        return item in self.bookmarks
    
    def __iter__(self):
        return iter(self.bookmarks)

    def append(self, val):
        self.bookmarks.append(val)

    def extend(self, aseq):
        [self.bookmarks.append(a) for a in aseq]

    def _reindex(self):
        for bm in self.bookmarks:
            if bm.id not in self.id_dict:
                self.id_dict[bm.id] = bm


