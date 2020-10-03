"""
Extension to trigger the pydoctor API builds as part of the Sphinx build.

This is created to have API docs created on Read the docs.
"""
import os

from sphinx.builders import Builder
from sphinx.util import logging


from twisted.python._release import BuildAPIDocsScript


logger = logging.getLogger(__name__)




class PyDoctorBuilder(Builder):
   """
   Trigger pydoctor HTML generation.
   """
   name = 'pydoctor'
   format = 'pydoctor'
   out_suffix = '.html'

   def write(self, *args):
      """
      Called when build process starts.
      """
      source = self.app.config.apidocs['source']
      destination = os.path.join(
         self.outdir, self.app.config.apidocs['destination'])

      logger.info('pydoctor API docs build from %s to %s.' % (
         source, destination))
      BuildAPIDocsScript().main([source, destination])
      logger.info('pydoctor API docs done.')

   def finish(self):
      pass


def setup(app):
   """
   This is called by Sphinx extension system.
   """
   app.add_config_value(
      'apidocs',
      {'source': 'src', 'destination': 'api'},
      'env',
      )
   app.add_source_suffix('.pydoctor', 'pydoctor')
   app.add_builder(PyDoctorBuilder)
