import os
import cPickle

from twisted.trial import unittest

from twisted.application import service
from twisted.scripts import twistd


class MockServiceMaker(object):
    """
    A non-implementation of L{twisted.scripts.mktap.IServiceMaker}.
    """
    tapname = 'ueoa'
    def makeService(self, options):
        """
        Take a L{usage.Options} instance and return a
        L{service.IService} provider.
        """
        self.options = options
        self.service = service.Service()
        return self.service



class TapFileTest(unittest.TestCase):
    """
    Test twistd-related functionality that requires a tap file on disk.
    """

    def setUp(self):
        """
        Create a trivial Application and put it in a tap file on disk.
        """
        self.tapfile = self.mktemp()
        cPickle.dump(service.Application("Hi!"), file(self.tapfile, 'w'))


    def test_getApplicationWithTapFile(self):
        """
        Ensure that the getApplication call that 'twistd -f foo.tap'
        makes will load the Application out of foo.tap.
        """
        config = twistd.ServerOptions()
        config.parseOptions(['-f', self.tapfile])
        application = twistd.getApplication(config)
        self.assertEquals(service.IService(application).name, 'Hi!')



class TwistdTest(unittest.TestCase):

    def test_getApplicationWithSubcommand(self):
        """
        getApplication should honor subCommands as
        L{twisted.scripts.mktap.IServiceMaker} plugins, and create an
        Application with the service that the ServiceMaker creates.
        """
        config = twistd.ServerOptions()
        msm = MockServiceMaker()
        # Set up a config object like it's been parsed with a subcommand
        config.loadedPlugins = {'test_command': msm}
        config.subOptions = object()
        config.subCommand = 'test_command'

        application = twistd.getApplication(config)
        self.assertIdentical(
            msm.options, config.subOptions, 
            "ServiceMaker.makeService needs to be passed the correct "
            "sub Command object.")
        self.assertIdentical(
            msm.service, service.IService(application).services[0],
            "ServiceMaker.makeService's result needs to be set as a child "
            "of the Application.")


    def test_postOptionsSubCommandCausesNoSave(self):
        """
        postOptions should set no_save to True when a subcommand is used.
        """
        config = twistd.ServerOptions()
        config.subCommand = 'ueoa'
        config.postOptions()
        self.assertEquals(config['no_save'], True)


    def test_postOptionsNoSubCommandSavesAsUsual(self):
        """
        If no sub command is used, postOptions should not touch no_save.
        """
        config = twistd.ServerOptions()
        config.postOptions()
        self.assertEquals(config['no_save'], False)
