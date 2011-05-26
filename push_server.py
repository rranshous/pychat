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


class Room():
    """
    A room is a collection of streams which subscribe to the room
    any text sent to the room is sent out to the people listening
    in the room
    """

    def __init__(self,name):
        log.debug('adding room: %s' % name)

        self.name = name

        self.streams = []

    def add_stream(self,stream):
        """
        adds a new stream for listening in this room
        """
        log.debug('%s: adding stream' % self.name)

        if stream not in self.streams:
            self.streams.append(stream)

    def remove_stream(self,stream):
        """
        removes a stream from the room
        """

        log.debug('%s: removing stream' % self.name)

        try:
            self.streams.remove(stream)
        except IndexError:
            return False

        return True

    def send_message(self,message,sender_stream):
        """
        relays the message to all streams listening
        for messages in this room
        """

        log.debug('%s: sending message %s' % (self.name,message))

        # relay the message to the streams
        for stream in self.streams:
            # don't want to broadcast back to sender
            if stream is sender_stream:
                continue
            stream.write(message)
            stream.write('\r\n\r\n')


class House():
    """
    collects rooms
    """

    def __init__(self):
        self.rooms = {}

    def get(self, name):
        """
        returns the room who's name u passed
        creates it if it doesn't exist yet
        """

        if not name in self.rooms:
            log.debug('adding new room: %s' % name)
            room = Room(name)
            self.rooms[name] = room
        else:
            room = self.rooms.get(name)

        return room


class Handler():
    """
    handles connections, adds / removes
    them from rooms, notifies rooms of new messages
    """

    def __init__(self,stream,house):
        self.stream = stream
        self.house = house

        self.listening_rooms = []

    def __call__(self,data):
        """ socket receives more data """

        # parse the args they sent us
        args = self.parse_args(data)

        log.debug('args: %s' % args)

        # see if they want to add any rooms
        if 'add-room' in args:
            log.debug('found add room in args')
            self.add_rooms(args.get('add-room').split(','))

        # remove from a room?
        if 'remove-room' in args:
            log.debug('found remove room in args')
            self.remove_rooms(args.get('remove_room').split(','))

        # if they have broadcast in there, they want to send a message
        # to some rooms
        if 'broadcast' in args:
            log.debug('found broadcast in args')

            # if they specify rooms, pull them, we don't have to
            # be a subscriber to braodcast to a room
            if 'room' in args:
                log.debug('found room in args: %s' % args.get('room'))

                rooms = []
                for name in args.get('room').split(','):
                    room = self.house.get(name)
                    if room:
                        rooms.append(room)

            # if no rooms are specified, all rooms they listen to
            else:
                rooms = self.listening_rooms

            # they want to broadcast a message
            for room in rooms:
                room.send_message(args.get('message'),self.stream)

        self.done()

    def done(self):
        self.stream.write('DONE\r\n\r\n')
        self.stream.read_until('\r\n\r\n',self)
    
    def add_rooms(self,room_names):
        """
        adds listeners to specified rooms, by name
        """

        log.debug('adding rooms: %s' % room_names)

        # pull the room for each name
        for name in room_names:
            room = self.house.get(name)

            # add our stream as a listener
            room.add_stream(self.stream)

            # note we are listening
            self.listening_rooms.append(room)

    def remove_rooms(self,room_names):
        """
        removes our listener from rooms by name
        """

        log.debug('removing rooms: %s' % room_names)

        # pull the rooms
        for name in room_names:
            room = self.house.get(name)

            # remove our stream as a listener
            room.remove_stream(self.stream)

            # note we are listening
            self.listening_rooms.remove(room)

    def parse_args(self,data):
        # args are supposed to be k:v\n
        # we should get k/v pairs
        # one per line ':' seperated
        args = {}
        for line in data.split('\r\n'):
            parts = [x.strip() for x in line.split(':',1)]
            if len(parts) == 2:
                args[parts[0].lower()] = parts[1]
        return args


class Server():
    
    def handle_accept(self, fd, events):
        log.debug('accepting')

        conn, addr = self._sock.accept()
        stream = iostream.IOStream(conn)
        handler = Handler(stream,self.house)
        stream.read_until('\r\n\r\n',handler)

    def start(self, host, port):
        # let those listening know we are about to begin

        log.debug('plugin server starting: %s %s'
                  % (host,port))

        # startup our room collection
        self.house = House()

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

