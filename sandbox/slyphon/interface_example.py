#!/usr/bin/python2.3
import zope.interface as zi

from twisted.python.components import registerAdapter

class IBar(zi.Interface):
    alcoholicBeverages = zi.Attribute("a list of available drinks")
    def gimmeADrink():
        """give me one of whatever your serving"""

class Bar(object):
    def __init__(self):
        self.alcoholicBeverages = ["JD", "SoCo", "Samuel Adams"]

    def gimmieADrink(self):
        return self.alcoholicBeverages[1]


class YourBuddysHouse(object):
    def __init__(self):
        self.beers = ["bud", "guiness", "fosters"]

    
class AdaptYourBuddysHouseToBar(object):
    zi.implements(IBar) # <-- forgot this
    def __init__(self, original):
        self.original = original
        self.alcoholicBeverages = self.original.beers

    def gimmeADrink(self):
        return self.original.beers[2]


registerAdapter(AdaptYourBuddysHouseToBar, YourBuddysHouse, IBar)

def main():
    ybh = YourBuddysHouse()
    print "ybh.beers: %r" % (ybh.beers,)
    # hmm, i really wish that my friend's house was
    # more like a bar, because i'm really dumb and I only
    # know how to get a list of alcoholic beverages or 
    # ask an object .gimmeADrink()

    ibarAdapter = IBar(ybh)
    print "ibarAdapter.alcoholicBeverages: %r" % (ibarAdapter.alcoholicBeverages,)

    print "IBar(ybh).gimmeADrink(): %s" % IBar(ybh).gimmeADrink()


if __name__ == "__main__":
    main()
