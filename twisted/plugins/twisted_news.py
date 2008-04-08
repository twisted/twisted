# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.application.service import ServiceMaker

TwistedNews = ServiceMaker(
    "Twisted News",
    "twisted.news.tap",
    "A news server.",
    "news")
