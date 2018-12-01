$ pip install twisted
Collecting twisted
  Using cached https://files.pythonhosted.org/packages/5d/0e/a72d85a55761c2c3ff1cb968143a2fd5f360220779ed90e0fadf4106d4f2/Twisted-18.9.0.tar.bz2
    Complete output from command python setup.py egg_info:
    Couldn't find index page for 'twisted' (maybe misspelled?)
    No local packages or download links found for twisted>=16.4.0
    Traceback (most recent call last):
      File "<string>", line 1, in <module>
      File "/tmp/pip-install-SycYjI/twisted/setup.py", line 20, in <module>
        setuptools.setup(**_setup["getSetupArgs"]())
      File "/usr/lib/python2.7/distutils/core.py", line 111, in setup
        _setup_distribution = dist = klass(attrs)
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/setuptools/dist.py", line 221, in __init__
        self.fetch_build_eggs(attrs.pop('setup_requires'))
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/setuptools/dist.py", line 245, in fetch_build_eggs
        parse_requirements(requires), installer=self.fetch_build_egg
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/pkg_resources.py", line 580, in resolve
        dist = best[req.key] = env.best_match(req, self, installer)
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/pkg_resources.py", line 825, in best_match
        return self.obtain(req, installer) # try and download/install
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/pkg_resources.py", line 837, in obtain
        return installer(requirement)
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/setuptools/dist.py", line 294, in fetch_build_egg
        return cmd.easy_install(req)
      File "/usr/local/lib/python2.7/dist-packages/distribute-0.6.28-py2.7.egg/setuptools/command/easy_install.py", line 592, in easy_install
        raise DistutilsError(msg)
    distutils.errors.DistutilsError: Could not find suitable distribution for Requirement.parse('twisted>=16.4.0')
    
    ----------------------------------------
Command "python setup.py egg_info" failed with error code 1 in /tmp/pip-install-SycYjI/twisted/

Might want to enable issues.
