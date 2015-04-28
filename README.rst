****************************
Mopidy-WAMPFrontend
****************************

.. image:: https://img.shields.io/pypi/v/Mopidy-WAMPFrontend.svg?style=flat
    :target: https://pypi.python.org/pypi/Mopidy-WAMPFrontend/
    :alt: Latest PyPI version

.. image:: https://img.shields.io/pypi/dm/Mopidy-WAMPFrontend.svg?style=flat
    :target: https://pypi.python.org/pypi/Mopidy-WAMPFrontend/
    :alt: Number of PyPI downloads

.. image:: https://img.shields.io/travis/nethack42/mopidy-wampfrontend/master.svg?style=flat
    :target: https://travis-ci.org/nethack42/mopidy-wampfrontend
    :alt: Travis CI build status

.. image:: https://img.shields.io/coveralls/nethack42/mopidy-wampfrontend/master.svg?style=flat
   :target: https://coveralls.io/r/nethack42/mopidy-wampfrontend?branch=master
   :alt: Test coverage

This extension provides a WAMP frontend for the popular Mopidy music server by connecting to a WAMP enabled router such as `crossbar.io <http://crossbar.io>`. Based on the jsonrpc module shipped with mopidy the whole API is exposed to the WAMP router as Remote Procedure Calls (RPC). Mopidy events will also be published on the WAMP router.

   This extension does NOT include a WAMP (Web Application Messaging Protocol) router. 


Features
========

Currently the following features have been implemented:

 - Complete mopidy core API is exposed to the WAMP router
 - WAMP realm is configurable via mopidy config
 - WebSocket and WebSocket-over-SSL is supported
 - Raw-TCP socket support
 - Debug options for WAMP and autobahn


Problems & Missing Features
===========================

In order for a final 1.0 release, the following problems must be solved and missing features must be implemented:

 - Use a global IOLoop instead of a local TornadoReactor (for twisted support). This might require a change in the current Mopidy-HTTP frontend. 
 - WAMP Authentication is currently not supported
 - Currently based on the mopidy core.utils.jsonrpc which (according to Mopidy documentation) is a bad idea


Installation
============

Install by running::

    pip install Mopidy-WAMPFrontend

Or, if available, install the Debian/Ubuntu package from `apt.mopidy.com
<http://apt.mopidy.com/>`_.


Configuration
=============

Before starting Mopidy, you must add configuration for
Mopidy-WAMPFrontend to your Mopidy configuration file::

    [wampfrontend]
    enabled = true
    router = ws://127.0.0.1:8080/ws
    debug_wamp = false
    debug_autobahn = false
    enable_twisted_log = false


Project resources
=================
- `Source code <https://github.com/nethack42/mopidy-wampfrontend>`_
- `Issue tracker <https://github.com/nethack42/mopidy-wampfrontend/issues>`_
- `Development branch tarball <https://github.com/nethack42/mopidy-wampfrontend/archive/master.tar.gz#egg=Mopidy-WAMPFrontend-dev>`_


Changelog
=========

v0.1.0 (UNRELEASED)
----------------------------------------

- Initial release.
