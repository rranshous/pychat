import socket
from tornado import ioloop, iostream
import tornado.options
from tornado.options import define, options
from time import time
from collections import deque, namedtuple

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


"""
A WSGI server which supports chat and events
"""

if __name__ == '__main__':
    
    log.debug('parsing command line')
    tornado.options.parse_command_line()

    ioloop.IOLoop.instance().start()
