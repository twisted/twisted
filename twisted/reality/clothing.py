
"""
Clothing support for twisted reality.
"""

import thing
import error

slots = [
    "crown",
    "left eye",
    "right eye",
    "left ear",
    "right ear",

    "neck",
    "chest",

    "left arm",
    "right arm",
    "left wrist",
    "right wrist",
    "left hand",
    "right hand",
    "left fingers",
    "right fingers",

    "waist",
    "left leg",
    "right leg",
    "left ankle",
    "right ankle",
    "left foot",
    "right foot"
    ]

def new_slot_dict():
    new={}
    for slot in slots:
        new[slot]=[None]
    return new


def clothing_descript(player):
    desc=[player.capHeShe, ' is wearing ']
    try:
        clothes = player.clothing
    except AttributeError:
        return '' # %s is naked!!
    descd=[]
    for slot in slots:
        item=clothes[slot][-1]
        if item and item not in descd:
            if descd:
                desc.append(', ')
            desc.append(item.wornAppearance)
            descd.append(item)

    if len(desc) > 3:
        desc.insert(len(desc)-1,'and ')
    if len(desc) < 3:
        return ''
    desc.append('.')
    return desc


def get(player, slot):
    """clothing.get(player, slot name) -> Clothing or None
    Returns a piece of clothing if a player is wearing something in that slot,
    or None if not.
    """
    assert slot in slots, "That's not a valid slot: %s" % slot
    try:
        return player.clothing[slot]
    except KeyError:
        return None
    except AttributeError:
        return None

class Clothing(thing.Thing):
    """
    A superclass for anything which can be worn.
    """
    wearer = None
    clothing_appearance = None


    def _wear(self, actor):
        """pre hook for `wear'."""


    def _remove(self, actor):
        """pre hook for `remove'."""


    def wear(self, player):
        """ Cause a particular piece of clothing to be worn by a player.
        """
        self._wear(player)
        try:
            clothes = player.clothing
        except:
            clothes = new_slot_dict()
            player.clothing = clothes

        for location in self.clothing_slots:
            clothes[location].append(self)

        self.wearer = player
        self.component = 1
        # TODO: add myself as an observer for name changes...
        player.describe('clothing',clothing_descript(player))

    def remove(self, actor):
        """ Remove a piece of clothing.
        """
        self._remove(actor)
        if self.wearer:
            wearer=self.wearer
            clothes=self.wearer.clothing
            for location in self.clothing_slots:
                cloth=clothes[location][-1]
                if cloth is not self:
                    raise error.Failure("You'd have to remove ",cloth," first.")
            for location in self.clothing_slots:
                clothes[location].pop()
            self.component = 0
            self.wearer = None
            wearer.describe('clothing',clothing_descript(wearer))

    def wornAppearance(self,observer):
        if self.clothing_appearance:
            return self.clothing_appearance
        return self.aan(observer) + self.shortName(observer)

    def verb_wear(self, sentence):
        if self.wearer:
            error.Failure("That's already being worn.")
        self.wear(sentence.subject)

    def verb_remove(self, sentence):
        if sentence.subject is not self.wearer:
            error.Failure("You're not wearing that.")
        self.remove(sentence.subject)


class Shirt(Clothing):
    clothing_slots = ["chest",
                      "left arm",
                      "right arm"]


class Pants(Clothing):
    clothing_slots = ["left leg",
                      "right leg"]


class Cloak(Clothing):
    clothing_slots = ["right arm",
                      "left arm",
                      "left leg",
                      "right leg"]


class Gloves(Clothing):
    clothing_slots = ["right hand",
                      "left hand"]


class Robe(Clothing):
    clothing_slots = ["right arm",
                      "left arm",
                      "left leg",
                      "right leg"]


class Hat(Clothing):
    clothing_slots = ["crown"]


class Necklace(Clothing):
    clothing_slots = ["neck"]


class Cape(Clothing):
    clothing_slots = ["neck"]


class Shoes(Clothing):
    clothing_slots=["left foot",
                    "right foot"]


class Socks(Clothing):
    clothing_slots=["left foot",
                    "right foot"]


class Shorts(Clothing):
    clothing_slots=Pants.clothing_slots


class Belt(Clothing):
    clothing_slots=['waist']


class Tie(Clothing):
    clothing_slots=['neck']


class Tunic(Clothing):
    clothing_slots=['chest']


class Blindfold(Clothing):
    # TODO: make this actually blind you!
    clothing_slots=['left eye',
                    'right eye']


class Coat(Clothing):
    # TODO: make this openable/closable!
    clothing_slots=['left arm',
                    'right arm']


class Spectacles(Clothing):
    clothing_slots=['left eye',
                    'right eye',
                    'right ear',
                    'left ear']


