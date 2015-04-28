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

from threading import Thread, currentThread
from Queue import Queue, Empty as QueueEmpty

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
        ''' Executed when the session is joined a realm
            Registers all API calles from the core actor proxy on the WAMP router '''

        assert self.factory._client == None, \
            'WAMPFrontend: A client session has already been created'
        self.factory._client = self

        class ResultWrapper(object):
            ''' Unwraps a methods future result and provides an model encoded dictonary '''
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

    @inlineCallbacks
    def on_event(self, event, **kwargs):
        logger.info("WAMPFrontend: Publishing event '%s' %s" % (event, kwargs))
        yield self.publish(event, kwargs)

    def onDisconnect(self):
	''' Executed on disconnect '''
        logger.info("WAMPFrontend: connection to WAMP router lost")
        self.factory._client = None
	self.config.extra['frontend'].schedule( self.config.extra['frontend'].client_connect )


def url_to_client_string(url):
    if url.split(":")[0] in [ "ws" ]:
        proto = "tcp"
    elif url.split(":")[0] in [ "wss" ]:
        proto = "ssl"

    host_port = url.split("/")[2]
    return "%s:%s" % (proto, host_port)


class WAMPFrontend(pykka.ThreadingActor, core.CoreListener):
    ''' Web Application Messaging Protocol frontend for Mopidy.
        On startup an additional thread running a local Tornado 
        IOLoop will be created '''

    def __init__(self, config, core):
        ''' initialize the frontend 
            `config` is a dict holding Mopidy configuration values
            `core` is a Mopidy core actor proxy '''
        super(WAMPFrontend, self).__init__()
        self.core = core
        self.config = config
        self._loop = None
        self._reactor = None
        self._session = None


    def on_start(self):
        ''' start up the WAMP frontend by creating a session factory and 
            running a local IOLoop'''
        logger.info("WAMPFrontend started successfully")

        if self.config["wampfrontend"]["enable_twisted_log"]:
            log.startLogging(sys.stdout)

        self._prepare_local_ioloop()
        
        th = Thread(target=self._run_local_ioloop)
        th.deamon = True
        th.start()

	self.schedule( self.client_connect )


    def client_connect(self):
        client = clientFromString(self._reactor, url_to_client_string(self.config['wampfrontend']["router"]))
        transport = self._prepare_transport()
        logger.info('WAMPFrontend: connecting client (from thread: %s)' % currentThread()) 
        client.connect(transport)
 

    def _prepare_transport(self):
        ''' Prepare a transport factory '''
        assert self._reactor, \
            'WAMPFrontend: cannot create transport without an IOLoop and a TornadoReactor'

        config = types.ComponentConfig(
            realm = self.config['wampfrontend']['realm'],
            extra = {
                'core': self.core,
                'frontend': self })
        session = wamp.ApplicationSessionFactory(config=config)
        session.session = WAMPFrontendComponent

        # Add a reference toe the frontend object (ourself)
        session._frontend = self
        
        # Add a reference the the ApplicationSession created
        # since we are a client, there will be only one session at all
        session._client = None

        # Now also store a reference to the session factory for us
        self._session = session
        
        transport = websocket.WampWebSocketClientFactory(
            session,
            url = self.config['wampfrontend']['router'],
            debug = self.config['wampfrontend']['debug_autobahn'],
            debug_wamp = self.config['wampfrontend']['debug_wamp'])
        return transport


    def _prepare_local_ioloop(self):
        ''' Prepare the local Torando IOLoop used for the  twisted TornadoReactor '''
        assert not self._loop, \
            'WAMPFrontend: local IOLoop already initialized'
        try:
            self._loop = IOLoop()
        except Exception as e:
            logger.warn('WAMPFrontend: unable to create a local IOLoop: %s' % e)
            raise e

        try:
            self._reactor = TornadoReactor(self._loop)
        except Exception as e:
            logger.warn('WAMPFrontend: unable to create local TornadoReactor: %s' % e)
            raise e

        
    def _run_local_ioloop(self):
        ''' Start the local IOLoop in a separate thread '''
        assert self._loop, \
           'WAMPFrontend has not been started yet. Unable to run IOLoop'
        assert isinstance(self._loop, IOLoop), \
           'Invalid local IO-loop type: %s' % type(self._loop)
        loop = self._loop
        try:
            logger.info('WAMPFrontend: Starting local IOloop (%s) in thread %s' % (repr(loop), currentThread()))
            loop.start()
        except Exception as e:
            logger.warn('WAMPFrontend: cought exception on IOLoop.start(): %s' % e)
        finally: 
       	    logger.info("WAMPFrontend: Local IOLoop stopped. Closing it ...")
            loop.close()
            if self._loop:
                self._loop = None


    def _stop_local_ioloop(self):
        ''' Request the local IOLoop to stop '''
        assert self._loop, \
           'WAMPFrontend: frontend has not been started yet. Unable to stop IOLoop'
        assert isinstance(self._loop, IOLoop), \
           'WAMPFrontend: Invalid local IO-loop type: %s' % type(self.loop)

        loop = self._loop
        self._loop = None
        loop.add_callback(loop.stop)
        logger.info("WAMPFrontend: stopping local IOLoop ...")
        try:
            loop._waker.wake()
        except Exception as e:
            logger.warn('WAMPFrontend: cought exception on IOLoop._waker.wake(): %s' % e)


    def schedule(self, function, *args, **kwargs):
        ''' Schedule a function to be called during the next IOLoop iteration '''
        assert self._loop, \
           'WAMPFrontend has not been started yet. Unable to run IOLoop'
        assert isinstance(self._loop, IOLoop), \
           'WAMPFrontend: Invalid local IO-loop type: %s' % type(self._loop)
        logger.debug('WAMPFrontend: scheduled call for IOLoop: %s' % function)
        self._loop.add_callback( function, *args, **kwargs )
        
        
    def on_stop(self):
        logger.info("WAMPFrontend stopping ...")
        self._stop_local_ioloop()

    def on_event(self, event, **kwargs):
        ''' Queue an incoming mopidy event to be published '''
        if self._session._client:
             self.schedule( self._session._client.on_event, event, **kwargs )
             logger.debug("WAMPFrontend: scheduled event publishing for %s" % event)
