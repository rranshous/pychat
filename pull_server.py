import socket
from tornado import ioloop, iostream
import tornado.options
from tornado.options import define, options
from time import time
from collections import deque, namedtuple
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# simple server for pub / sub text transmission

Message = namedtuple('Message',['timestamp','body'])

class MessageQueue():
    def __init__(self,maxlen):
        self.maxlen = maxlen
        self.rooms = {}

    def getfrom(self,room,last_check=None):
        """ returns back all the messages since the last check
            for the given room """

        log.debug('getting: %s %s' % (room,last_check))
        log.debug('messages: %s' % (0 if not room in self.rooms
                                    else len(self.rooms.get(room))))
        
        # see if we have any messages for that room
        last_check = int(last_check) or 0

        # go through the message's in the room
        if room in self.rooms and len(self.rooms.get(room)) > 0:
            # messages are ordered newest to oldest
            for msg in self.rooms.get(room):
                if msg.timestamp > last_check:
                    yield msg.body

    def add_message(self,message,room):
        """ adds a msg to the queue """

        # strip that message
        message = message.strip()

        log.debug('adding message: %s %s' % (message,room))

        # add a dequeue for the room if its not there
        if room not in self.rooms:
            d = deque(maxlen=self.maxlen)
            self.rooms[room] = d

        # add the msg to the collection
        self.rooms.get(room).appendleft(
            Message(time(),message))

        # return the message for good measure
        return self.rooms.get(room)[-1]

class Handler():
    def __init__(self,stream,messages):
        self.stream = stream
        self.messages = messages
        self.args = {}

    def __call__(self,data):
        """
        handle data coming in
        """

        log.debug('got data: %s' % (len(data)))

        # if we don't have args yet, these must be them
        if not self.args:
            self.parse_args(data)

        else:
            # we've already got args, must
            # be a message
            self.handle_send(data)

    def parse_args(self,data):
        log.debug('parsing args')

        # we should get k/v pairs
        # one per line ':' seperated
        for line in data.split('\r\n'):
            parts = [x.strip() for x in line.split(':',1)]
            if len(parts) == 2:
                self.args[parts[0].lower()] = parts[1]

        # set our last update to 0 if we didn't get one
        self.args['last-check'] = 0

        log.debug('args: %s' % self.args)

        # see if this is a request for messages
        # or someone sending a message
        if 'broadcast' in self.args:
            # if they are sending us a message, we now
            # need to listen for the message
            self.stream.read_until('\r\n\r\n',self)

        else:
            self.handle_check_messages()

    def handle_send(self,data):
        log.debug('handling send: %s' % (data))

        # add our message
        self.messages.add_message(data,self.args.get('room'))

        self.stream.write('SUCCESS')
        self.end_response()

    def handle_check_messages(self):
        log.debug('handling check messages')

        # the response starts with a json list open
        self.stream.write('[')

        # now each of our json text obj
        for msg in self.messages.getfrom(self.args.get('room'),
                                         self.args.get('last-check')):
            self.stream.write(msg)

        # and now close our list
        self.stream.write(']')
        self.end_response()

    def end_response(self):
        self.stream.write('\r\n\r\n')
        self.args = {}
        self.stream.read_until('\r\n\r\n',self)

class Server():
    
    def handle_accept(self, fd, events):
        log.debug('accepting')

        conn, addr = self._sock.accept()
        stream = iostream.IOStream(conn)
        handler = Handler(stream,self.message_queue)
        stream.read_until('\r\n\r\n',handler)

    def start(self, host, port):
        # let those listening know we are about to begin

        log.debug('plugin server starting: %s %s'
                  % (host,port))

        # startup our message queue
        self.message_queue = MessageQueue(100)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self._sock.setblocking(0)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host,port))
        self._sock.listen(128)
        ioloop.IOLoop.instance().add_handler(self._sock.fileno(),
                                             self.handle_accept,
                                             ioloop.IOLoop.READ)

        self.host = host
        self.port = port



define('host', default="0.0.0.0", help="The binded ip host")
define('port', default=8005, type=int, help='The port to be listened')

if __name__ == '__main__':
    
    log.debug('parsing command line')
    tornado.options.parse_command_line()

    log.debug('creating server')
    server = Server()

    log.debug('starting server')
    server.start(options.host, options.port)

    ioloop.IOLoop.instance().start()

