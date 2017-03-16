import socket, os, sys, binascii, time, datetime, threading, logging, importlib
import re

"""
Rcon protocol class.
Used to establish the connection and to send keep-alive packages
Also it provides some default commands, like kickAll, sendChat , lockServer, etc...

The module loader <loadmodule(name, class)> allows the use of the following events:
- OnConnected
- OnReconnected
- OnPlayerConnect
- OnPlayerDisconnect
- OnChat
"""
class Rcon():

    Timeout = 60 # When the connection did not received any response after this period
    KeepAlive = 30 # KeepAlive must always be lower than Timeout, otherwise the Timeout occurs
    ConnectionRetries = 5 # Try to reconnect (at startup) X times and...
    ConnectionInterval = 10 # ... try it every 10 seconds. Example (1 + 5 tries X 10 seconds = 60 seconds until server should be up)

    """
    constructor: create an instance by passing ip, password and port as arguments
    """
    def __init__(self, ip, password, Port):
        # constructor parameters
        self.ip = ip
        self.password = password
        self.port = int(Port)

        # module instances as dict (to have them loaded only once)
        self.__instances = {}

        # last timestamp used for checkinh keepalive
        self.isExit = False
        self.isAuthenticated = False
        self.retry = 0

        self.lastcmd = ""

        # server message receive filters
        self.receiveFilter = [
            # receive all players
            ("\n(\d+)\s+(.*?)\s+([0-9]+)\s+([A-z0-9]{32})\(.*?\)\s(.*)", self.__players, True),
            # receive missions
            ("\n(.*\.[A-z0-9_-]+\.pbo)", self.__missions, True),
            # when player is connected
            ("Verified GUID \(([A-Fa-f0-9]+)\) of player #([0-9]+) (.*)", self.__playerConnect, False),
            # when player is disconnected
            ("Player #([0-9]+) (.*?) disconnected", self.__playerDisconnect, False),
            # chat messages
            ("\((\w+)\) (.*?): (.*)", self.__chatMessage, False),
        ]

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as serr:
            print ('Failed to create socket')
            logging.error('rconprotocol: Failed to created socket: {}'.format(serr))
            sys.exit()

    """
    public: load additional modules.
    @param string name - module name without .py suffix
    @param string cls  - class name to create an instance of
    """
    def loadmodule(self, name, cls, *args):
        if type(self).__name__ == cls:
            return self

        key = "%s.%s" % (name, cls)
        if not key in self.__instances.keys():
            mod = importlib.import_module('lib.' + name)
            classT = getattr(mod, cls)
            clsObj = classT(self, *args)

            self.__instances[key] = clsObj

        return self.__instances[key]

    """
    private: threaded method sending keepAlive messages to the server.
    Use the KeepAlive constant to define the interval
    """
    def _keepAliveThread(self):
        time.sleep(self.KeepAlive)
        self.sendCommand(None)
        if not self.isExit:
            self._keepAliveThread()

    """
    private: to calculate the crc (Battleye).
    More Info: http://www.battleye.com/downloads/BERConProtocol.txt
    """
    def __compute_crc(self, Bytes):
        buf = memoryview(Bytes)
        crc = binascii.crc32(buf) & 0xffffffff
        crc32 = '0x%08x' % crc
        return int(crc32[8:10], 16), int(crc32[6:8], 16), int(crc32[4:6], 16), int(crc32[2:4], 16)

    """
    public: send individual server commands.
    @param string toSendCommand - any valid server command, like "#ban <playerid>"
    """
    def sendCommand(self, toSendCommand):
        if not self.isAuthenticated:
            logging.error('Command failed - Not Authenticated')
            return

        # request =  "B" + "E" + 4 bytes crc check + command
        command = bytearray()
        command.append(0xFF)
        command.append(0x01)
        command.append(0x00)

        if toSendCommand:
            logging.debug('Sending command "{}"'.format(toSendCommand))
            command.extend(toSendCommand.encode('utf-8','replace'))
        else:
            logging.debug('Sending keepAlive package')

        self.lastcmd = toSendCommand

        request = bytearray(b'BE')
        request.extend( self.__compute_crc(command) )
        request.extend(command)

        self.s.sendto(request ,(self.ip, self.port))

    """
    private: send the magic bytes to login as Rcon admin.
    More Info: http://www.battleye.com/downloads/BERConProtocol.txt
    """
    def _sendLogin(self, passwd):
        logging.debug('Sending login information')
        # request =  "B" + "E" + 4 bytes crc check + command

        command = bytearray()
        command.append(0xFF)
        command.append(0x00)
        command.extend(passwd.encode('utf-8','replace'))

        request = bytearray(b'BE')
        request.extend( self.__compute_crc(command) )
        request.extend(command)

        return request

    """
    private: accept server messages.
    More Info: http://www.battleye.com/downloads/BERConProtocol.txt
    """
    def _acknowledge(self, Bytes):
        
        command = bytearray()
        command.append(0xFF)
        command.append(0x02)
        command.extend(Bytes)

        request = bytearray(b'BE')
        request.extend( self.__compute_crc(command) )
        request.extend(command)

        seqNo = Bytes[0]

        logging.info('ACK seq:{}'.format(seqNo))

        return request

    """
    private: handle all incoming server messages from socket.recvfrom method
    @param unknown packet - received package
    """
    def __streamReader(self, packet):
        # reset the retries if from now one some connection problems occured
        self.retry = 0

        #ACKNOWLEDGE THE MESSAGE
        p = packet[0]
        try:
            if p[0:2] == b'BE' and self.isAuthenticated:
                self.s.sendto(self._acknowledge(p[8:9]), (self.ip, self.port))

        except:
            pass
        
        # Debug output the complete packet received from server
        logging.debug("[Server: %s:%s]: %s" % (self.ip, self.port, packet))

        stream = packet[0]

        # successfully authenticad packet received
        if stream[6:] == b'\xff\x00\x01':
            self.s.settimeout( self.Timeout )
            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, "Authenticated"))
            # Only do the below if this is the initial connect call
            if not self.isAuthenticated:
                self.isAuthenticated = True
                self.OnConnected()
            else:
                self.OnReconnected()
            return
        # when authentication failed, exit the program
        if stream[6:] == b'\xff\x00\x00':
            logging.error("Not Authenticated")
            exit()
        
        # ausume when the last command is empty, its a keepAlive packet
        if stream[6:8] == b'\xff\x01' and not self.lastcmd:
            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, "KeepAlive"))
            return

        # success message from the server for the previous command (or keep alive)
        if stream[6:9] == b'\xff\x01' and self.lastcmd:
            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, "ACK " + self.lastcmd))
        # all other packages and commands
        if len(stream[9:]) > 0:
            stream = stream[9:].decode('utf-8', 'replace')
            self.__parseResponse(stream)

            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, stream))

    def __players(self, pl):
        l = []
        for m in pl:
            l.append( Player(m[0], m[3], m[4]) )

        self.OnPlayers(l)
    
    def __missions(self, missions):
        self.OnMissions(missions)

    def __playerConnect(self, m):
        self.OnPlayerConnect( Player(m[1], m[0], m[2]) )

    def __playerDisconnect(self, m):
        self.OnPlayerDisconnect( Player(m[0], "", m[1]) )

    def __chatMessage(self, m):
        self.OnChat( ChatMessage( m[0], m[1], m[2]) )

    """
    private: parse the incoming message from __streamReader to provide eventing
    """
    def __parseResponse(self, msg):
        for x in self.receiveFilter:
            regex, action, multiline = x
            if multiline:
                m = re.findall(regex, msg)
                if len(m) > 0:
                    action(m)
                    break
            else:
                m = re.search(regex, msg)
                if m:
                    action(m.groups())
                    break

    """
    public: send a chat message to everyone
    @param string msg - message text
    """
    def sendChat(self, msg, ident = -1):
        self.sendCommand("say %s \"%s\"" % (ident,msg))

    """
    public: kick all players
    """
    def kickAll(self):
        logging.info('Kick All player before restart take action')

        for i in range(1, 100):
            self.sendCommand('kick %s' % (i))
            time.sleep(0.05)

    """
    public: lock the server (until next restart/unlock). So nobody can join anymore
    """
    def lockServer(self):
        self.sendCommand('#lock')
        time.sleep(1)

    """
    Event: when list of players is requested
    """
    def OnPlayers(self, playerList):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnPlayers', None)
            if func: func(playerList)

    """
    Event: when mission files are requested
    """
    def OnMissions(self, missionList):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnMissions', None)
            if func: func(missionList)

    """
    Event: when a player connects to the server
    """
    def OnPlayerConnect(self, player):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnPlayerConnect', None)
            if func: func(player)

    """
    Event: when a player disconnects from the server
    """
    def OnPlayerDisconnect(self, player):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnPlayerDisconnect', None)
            if func: func(player)

    """
    Event: Incoming chat messages
    @param ChatMessage chatObj - chat object containing channel and message
    """
    def OnChat(self, chatObj):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnChat', None)
            if func: func(chatObj)

    """
    Event: when program is successfully connected and authenticated to the server.
           This can perfectly be used in modules.
    """
    def OnConnected(self):
        # initialize keepAlive thread
        _t = threading.Thread(target=self._keepAliveThread)
        _t.daemon = True
        _t.start()

        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnConnected', None)
            if func: func()

    """
    Event: when program is successfully reconnected and authenticated to the server.
           This can perfectly be used in modules.
    """
    def OnReconnected(self):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnReconnected', None)
            if func: func()

    def OnAbort(self):
        for clsObj in self.__instances.values():
            func = getattr(clsObj, 'OnAbort', None)
            if func: func()

    """
    public: cancel all loops (keepAlive and others from modules) and send the final "exit" command to disconnect from server
    """
    def Abort(self):
        logging.info("Exit loop")
        self.isExit = True
        self.OnAbort()

    def connectAsync(self):
        _t = threading.Thread(target=self.connect, name='connectionThread')
        _t.daemon = True
        _t.start()

    """
    public: used to establish the connection to the server giving by constructor call
    """
    def connect(self):
        try:
            self.s.settimeout(self.ConnectionInterval)
            #Set the whole string
            logging.info('Connecting to {}:{} #{}'.format(self.ip, self.port, self.retry))
            self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))

            # receive data from client (data, addr)
            while not self.isExit:
                d = self.s.recvfrom(2048)           #1024 value crash on players request on full server
                self.__streamReader(d)

        # Connection timed out
        except socket.timeout as et:
            logging.error('Socket timeout: {}'.format(et))
            if self.retry < self.ConnectionRetries and not self.isExit:
                self.retry += 1
                self.connect()
            else:
                self.Abort()

        # Some problem sending data ??
        except socket.error as e:
            logging.error('Socket error: {}'.format(e))
            self.Abort()

        # Ctrl + C
        except (KeyboardInterrupt, SystemExit):
            logging.debug('rconprotocol.connect: Keyboard interrupted')
            self.Abort()

        except:
            logging.exception("Unhandled Exception")
            self.Abort()


"""
Player class commonly used for events OnPlayerConnect and OnPlayerDisconnect
"""
class Player():
    def __init__(self, no, guid, name):
        self.number = no
        self.guid = guid
        self.name = name
        self.allowed = False

    def Allow(self):
        self.allowed = True

    def Disallow(self):
        self.allowed = False

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
        
    @staticmethod
    def fromJSON(i):
        o = Player(i['number'], i['guid'], i['name'])
        if i['allowed']:
            o.Allow()
        return o

"""
Chat class commonly used for event OnChat
"""
class ChatMessage():
    def __init__(self, channel, sender, message):
        self.channel = channel.lower()
        self.sender = sender
        self.message = message
