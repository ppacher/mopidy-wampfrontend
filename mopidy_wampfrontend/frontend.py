import pykka
import logging

import sys
import json

from tornado.ioloop import IOLoop
from tornado.platform.twisted import TornadoReactor

from twisted.python import log
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import clientFromString

from autobahn.twisted import wamp, websocket
from autobahn.wamp import types

from threading import Thread

from mopidy import core, models
from mopidy.utils import jsonrpc

logger = logging.getLogger(__name__)

class WAMPFrontendComponent(wamp.ApplicationSession):
    
    ''' WAMP Application session 

    Responsible for handling communication between the remote WAMP router and
    mopidy. On a successful join all API calles available through the core
    actor are exposed to the WAMP router as remote procedure calls (RPC). Events received by the 
    CoreListener interface will automatically be published on the WAMP router. 
    '''
    
    @inlineCallbacks
    def onJoin(self, details):

        class ResultWrapper(object):
            def __init__(self, call):
                self._call = call

            def get(self, *args, **kwargs):
                result = self._call(*args, **kwargs).get()
                return json.loads(json.dumps(result, cls=jsonrpc.get_combined_json_encoder([models.ModelJSONEncoder])))

        logger.info("Connected to WAMP router")
        core_actor = self.config.extra['core']    

        inspector = jsonrpc.JsonRpcInspector(
            objects={
                'core.get_uri_schemes': core.Core.get_uri_schemes,
                'core.get_version': core.Core.get_version,
                'core.history': core.HistoryController,
                'core.library': core.LibraryController,
                'core.mixer': core.MixerController,
                'core.playback': core.PlaybackController,
                'core.playlists': core.PlaylistsController,
                'core.tracklist': core.TracklistController,
            })
        wrapper = jsonrpc.JsonRpcWrapper(
            objects={
                'core.describe': inspector.describe,
                'core.get_uri_schemes': core_actor.get_uri_schemes,
                'core.get_version': core_actor.get_version,
                'core.history': core_actor.history,
                'core.library': core_actor.library,
                'core.mixer': core_actor.mixer,
                'core.playback': core_actor.playback,
                'core.playlists': core_actor.playlists,
                'core.tracklist': core_actor.tracklist,
                })
        count = 0
        yield self.register(inspector.describe, 'core.describe')
        for func in inspector.describe().keys():
            yield self.register(ResultWrapper(wrapper._get_method(func)).get, func)
            count = count + 1
        logger.info("WAMPFrontend: Registered %d API calls" % count)

    def on_event(self, event, **kwargs):
	self.publish(event, kwargs)

        
    def onDisconnect(self):
        logger.info("Disconnected from WAMP router")
        self.config.extra['frontend'].connect()


def url_to_client_string(url):
    if url.split(":")[0] in [ "ws" ]:
        proto = "tcp"
    elif url.split(":")[0] in [ "wss" ]:
        proto = "ssl"

    host_port = url.split("/")[2]
    return "%s:%s" % (proto, host_port)

class WAMPFrontend(pykka.ThreadingActor, core.CoreListener):
    def __init__(self, config, core):
        super(WAMPFrontend, self).__init__()
        self.core = core
        self.config = config
        logger.info("Loaded WAMPFrontend")

    def on_start(self):
        logger.info("WAMPFrontend started successfully")

        self.loop = IOLoop()
        self.reactor = TornadoReactor(self.loop)
        logger.info("WAMPFrontend: TornadoReactor created")

        if self.config["wampfrontend"]["enable_twisted_log"]:
            log.startLogging(sys.stdout)

        # 1) create a WAMP application session factory
        component_config = types.ComponentConfig(realm=self.config['wampfrontend']['realm'], extra={'core': self.core, 'frontend': self.actor_ref.proxy()} )
        session_factory = wamp.ApplicationSessionFactory(config=component_config)
        session_factory.session = WAMPFrontendComponent    

        transport_factory = websocket.WampWebSocketClientFactory(
            session_factory, 
            url=self.config['wampfrontend']["router"], 
            debug=self.config['wampfrontend']["debug_autobahn"], 
            debug_wamp=self.config['wampfrontend']["debug_wamp"])    
        logger.info("WAMPFrontend: WampWebSocketClientFactory created")

        # 3) start the client from a Twisted endpoint
        client = clientFromString(self.reactor, url_to_client_string(self.config['wampfrontend']["router"]))
        client.connect(transport_factory)
        
        th = Thread(target=self.run_ioloop)
        th.deamon = True
        th.start()
        
    def run_ioloop(self):
        logger.info("WAMPFrontend: Starting local IOLoop")
        loop = self.loop
        loop.start()
        logger.info("WAMPFrontend: Local IOLoop stopped")
        loop.close()
        
    def on_stop(self):
        logger.info("WAMPFrontend stopping ...")
        loop = self.loop
        self.loop = None

        loop.add_callback(loop.stop)

        try:
            loop._waker.wake()
        except:
            pass

    def on_event(self, event, **kwargs):
        print("Received event: %s (%s)" % (event, kwargs))
