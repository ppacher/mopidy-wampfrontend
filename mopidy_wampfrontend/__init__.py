from __future__ import unicode_literals

import logging
import os

from mopidy import config, ext


__version__ = '0.1.0'

logger = logging.getLogger(__name__)

class Extension(ext.Extension):

    dist_name = 'Mopidy-WAMPFrontend'
    ext_name = 'wampfrontend'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
	schema['router'] = config.String(optional=True)
	schema['realm'] = config.String(optional=True)
	schema['debug_wamp'] = config.Boolean(optional=True)
	schema['debug_autobahn'] = config.Boolean(optional=True)
	schema['enable_twisted_log'] = config.Boolean(optional=True)
        return schema

    def setup(self, registry):
        from .frontend import WAMPFrontend
        registry.add('frontend', WAMPFrontend)
