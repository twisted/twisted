from twisted.python.rebuild import rebuild
import twisted.web.util as util
from twisted.web.woven.page import Page

class SiteRebuild(Page):
    def initialize(self, *args, **kwargs):
        Page.initialize(self, *args, **kwargs)
        self.template = """
<html></html>
"""
        import SiteRebuild
        rebuild(SiteRebuild)

        return util.redirectTo("http://localhost:7000/second_rebuild",kwargs['request'])

