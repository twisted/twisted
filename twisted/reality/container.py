import thing
import error

class Container(thing.Thing):
    """Container

    A convenience class, setting a few defaults for objects intended
    to be containers.
    """

    hollow = 1

    def verb_put(self, sentence):
        """put foo (in|on) container
        Place one object in another.
        """
        obj = sentence.directObject()
        sub = sentence.subject
        # no fair making things disappear!
        if obj == self:
            Failure("Some would say it's already there. Anyway, you cant do that.")
        if self.surface:
            prep = 'on'
        else:
            prep = 'in'
        if obj.place is not sub:
            Failure("You're not holding that.")
        obj.move(destination = self, actor = sub)
        sub.broadcastToPair(self,
            to_subject = ("You put ",obj," ",prep," ",self,"."),
            to_target = (), # I'm an inanimate object.  What do I care?
            to_other = (sub,' puts ',obj,' ',prep,' ',self,'.') )

    verb_put_in = verb_put
    verb_put_on = verb_put

class _Contents(Container):
    "Bookkeeping class for the contents of boxes."
    surface = 0
    def containedPhrase(self, observer, other):
        "calls back up one level."
        return self.location.containedPhrase(observer, other)

class Box(thing.Thing):
    surface = 0
    isOpen = 0
    closedDesc = ''
    openDesc = ''
    contained_preposition = 'in'

    def setup(self):
        self.description = {'open/close': self.closedDesc}
        self.contents = _Contents("$"+self.name + "'s contents")
        self.contents.location = self
        self.contents.component = 1

    def action_Open(self, actor):
        self.isOpen = 1
        self.contents.surface = 1
        self.description = {'open/close': self.openDesc}
        
    def action_Close(self, actor):
        self.isOpen = 0
        self.contents.surface = 0
        self.description = {'open/close': self.closedDesc}

    def verb_open(self, sentence):
        sentence.shouldOnlyHave('')
        if self.isOpen:
            error.Failure("It's already open.")
        else:
            self.action_Open(sentence.subject)

    def verb_close(self, sentence):
        sentence.shouldOnlyHave('')
        if not self.isOpen:
            error.Failure("It's already closed.")
        else:
            self.action_Close(sentence.subject)

    def verb_put_in(self, sentence):
        sentence.shouldOnlyHave('','in')
        if self.isOpen:
            sentence.directObject().move(self.contents, sentence.subject)
        else:
            error.Failure("It's closed.")

    def destroy(self):
        self.contents.destroy()
        thing.Thing.destroy(self)
