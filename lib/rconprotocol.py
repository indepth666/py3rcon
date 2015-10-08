import socket
import os
import sys
import binascii
import time, datetime
import threading
import logging
import importlib
import re


"""
Rcon protocol class.
Used to establish the connection and to send keep-alive packages
Also it provides some default commands, like kickAll, sendChat , lockServer, etc...

The module loader <loadmodule(name, class)> allows the use of the following events:
- OnConnected
- OnPlayerConnect
- OnPlayerDisconnect
- OnChat
"""
class Rcon():

    Timeout = 60 # When the connection did not received any response after this period
    KeepAlive = 40 # KeepAlive must always be lower than Timeout, otherwise the Timeout occurs
    ConnectionRetries = 5 # Try to reconnect (at startup) X times and...
    ConnectionInterval = 10 # ... try it every 10 seconds. Example (1 + 5 tries X 10 seconds = 60 seconds until server should be up)

    """
    constructor: create an instance by passing ip, password and port as arguments
    """
    def __init__(self, ip, password, Port, streamWriter=True):
        # constructor parameters
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter

        # module instances as dict (to have them loaded only once)
        self._instances = {}

        # connection handler
        self.handleConnect = []
        # player connect and disconnect handler
        self.handlePlayerConnect = []
        self.handlePlayers = []
        self.handlePlayerDisconnect = []
        # handle chat messages
        self.handleChat = []
        # handle Abort message
        self.handleAbort = []

        # last timestamp used for checkinh keepalive
        self.isExit = False
        self.isAuthenticated = False
        self.retry = 0
        self.lastcmd = ""

        # server message receive filters
        self.receiveFilter = (
            # receive all players
            ("\n(\d+)\s+(.*?)\s+([0-9]+)\s+([A-z0-9]{32})\(.*?\)\s(.*)", self.__players, True),
            # when player is connected
            ("Verified GUID \(([A-Fa-f0-9]+)\) of player #([0-9]+) (.*)", self.__playerConnect, False),
            # when player is disconnected
            ("Player #([0-9]+) (.*?) disconnected", self.__playerDisconnect, False),
            # chat messages
            ("\(([A-Za-z]+)\) (.*?): (.*)", self.__chatMessage, False)
        )

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
    def loadmodule(self, name, cls):
        if type(self).__name__ == cls:
            return self

        key = "%s.%s" % (name, cls)
        if not key in self._instances.keys():
            mod = importlib.import_module('lib.' + name)
            classT = getattr(mod, cls);
            clsObj = classT(self)

            if "OnConnected" in dir(clsObj):
                self.handleConnect.append(clsObj.OnConnected)
            if "OnPlayerConnect" in dir(clsObj):
                self.handlePlayerConnect.append(clsObj.OnPlayerConnect)
            if "OnPlayerDisconnect" in dir(clsObj):
                self.handlePlayerDisconnect.append(clsObj.OnPlayerDisconnect)
            if "OnPlayers" in dir(clsObj):
                self.handlePlayers.append(clsObj.OnPlayers)
            if "OnChat" in dir(clsObj):
                self.handleChat.append(clsObj.OnChat)
            if "OnAbort" in dir(clsObj):
                self.handleAbort.append(clsObj.OnAbort)

            self._instances[key] = clsObj

        return self._instances[key]

    """
    private: threaded method sending keepAlive messages to the server.
    Use the KeepAlive constant to define the interval
    """
    def _keepAliveThread(self):
        _counter = 0
        while not self.isExit:
            time.sleep(1)
            _counter += 1
            if _counter%self.KeepAlive == 0:
                self.sendCommand(None)

            if _counter > self.KeepAlive:
                _counter = 0

    """
    private: to calculate the crc (Battleye).
    More Info: http://www.battleye.com/downloads/BERConProtocol.txt
    """
    def _compute_crc(self, Bytes):
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
        command.append(0x00)       #sequence number, must be incremented

        if toSendCommand:
            logging.debug('Sending command "{}"'.format(toSendCommand))
            command.extend(toSendCommand.encode('utf-8','replace'))
        else:
            logging.debug('Sending keepAlive package')

        self.lastcmd = toSendCommand

        request = bytearray(b'BE')
        crc1, crc2, crc3, crc4 = self._compute_crc(command)
        request.append(crc1)
        request.append(crc2)
        request.append(crc3)
        request.append(crc4)
        request.extend(command)
        #try:
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
        crc1, crc2, crc3, crc4 = self._compute_crc(command)
        request.append(crc1)
        request.append(crc2)
        request.append(crc3)
        request.append(crc4)
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
        crc1, crc2, crc3, crc4 = self._compute_crc(command)
        request.append(crc1)
        request.append(crc2)
        request.append(crc3)
        request.append(crc4)
        request.extend(command)

        return request

    """
    private: handle all incoming server messages from socket.recvfrom method
    @param unknown packet - received package
    """
    def _streamReader(self, packet):
        # reset the retries if from now one some connection problems occured
        self.retry = 0

        #ACKNOWLEDGE THE MESSAGE
        p = packet[0]
        try:
            if p[0:2] == b'BE':

                #print(p[8:9])
                self.s.sendto(self._acknowledge(p[8:9]), (self.ip, self.port))
        except:
            pass

        #READ THE STREAM AND PRINT() IT
        if self.writeConsole is True:
            a = datetime.datetime.now()
            stream = packet[0]

            # successfully authenticad packet received
            if stream[6:] == "\xff\x00\x01":
                self.s.settimeout( self.Timeout )
                stream = "Authenticated"
                # Only do the below if this is the initial connect call
                if not self.isAuthenticated:
                    self.isAuthenticated = True
                    self.OnConnected()
            # when authentication failed, exit the program
            elif stream[6:] == "\xff\x00\x00":
                logging.error("Not Authenticated")
                exit()
            # success message from the server for the previous command (or keep alive)
            elif stream[6:] == "\xff\x01\x00" and self.lastcmd:
                stream = "ACK {}".format(self.lastcmd)
            elif stream[6:] == "\xff\x01\x00" and not self.lastcmd:
                stream = "KeepAlive"
            # all other packages and commands
            else:
                stream = stream[9:].decode('ascii', 'replace')
                self._parseResponse(stream)

            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, stream))
            logging.debug("[Server: %s:%s]: %s" % (self.ip, self.port, packet))


    def __players(self, pl):
        l = []
        for m in pl:
            l.append( Player(m[0], m[3], m[4]) )

        self.OnPlayers(l)

    def __playerConnect(self, m):
        self.OnPlayerConnect( Player(m[2], m[1], m[3]) )

    def __playerDisconnect(self, m):
        self.OnPlayerDisconnect( Player(m[1], "", m[2]) )

    def __chatMessage(self, m):
        self.OnChat( ChatMessage( m[1], m[2], m[3]) )

    """
    private: parse the incoming message from _streamReader to provide eventing
    """
    def _parseResponse(self, msg):
        for regex, action, multiline in self.receiveFilter:
            if multiline:
                m = re.findall(regex, msg)
                if len(m) > 0:
                    action(m)
                    break
            else:
                m = re.search(regex, msg)
                if m:
                    action(m.group())
                break


    """
    public: send a chat message to everyone
    @param string msg - message text
    """
    def sendChat(self, msg):
        self.sendCommand("say -1 \"%s\"" % msg)

    """
    public: kick all players
    """
    def kickAll(self):
        logging.info('Kick All player before restart take action')
        for i in range(1, 100):
            self.sendCommand('#kick {}'.format(i))
            time.sleep(0.1)

    """
    public: lock the server (until next restart/unlock). So nobody can join anymore
    """
    def lockServer(self):
        self.sendCommand('#lock')
        time.sleep(1)


    def OnPlayers(self, playerList):
        if len(self.handlePlayers) > 0:
            for pl in self.handlePlayers:
                pl(playerList)

    """
    Event: when a player connects to the server
    """
    def OnPlayerConnect(self, player):
        if len(self.handlePlayerConnect) > 0:
            for pconn in self.handlePlayerConnect:
                pconn(player)

    """
    Event: when a player disconnects from the server
    """
    def OnPlayerDisconnect(self, player):
        if len(self.handlePlayerDisconnect) > 0:
            for pdis in self.handlePlayerDisconnect:
                pdis(player)

    """
    Event: Incoming chat messages
    @param ChatMessage chatObj - chat object containing channel and message
    """
    def OnChat(self, chatObj):
        if len(self.handleChat) > 0:
            for cmsg in self.handleChat:
                cmsg(chatObj)

    """
    Event: when program is successfully connected and authenticated to the server.
           This can perfectly be used in modules.
    """
    def OnConnected(self):
        # initialize keepAlive thread
        _t = threading.Thread(target=self._keepAliveThread)
        _t.deamon = True
        _t.start()

        if len(self.handleConnect) > 0:
            for conn in self.handleConnect:
                conn()

    def OnAbort(self):
        if len(self.handleAbort) > 0:
            for abr in self.handleAbort:
                abr()

    def OnAbort(self):
        if len(self.handleAbort) > 0:
            for abr in self.handleAbort:
                abr()

    """
    public: check if program is about to exit
    """
    def IsAborted(self):
        return self.isExit

    """
    public: cancel all loops (keepAlive and others from modules) and send the final "exit" command to disconnect from server
    """
    def Abort(self):
        logging.info("Exit loop")
        self.isExit = True
        self.OnAbort()
        # send the final kill and force socket to call recvfrom (and dont wait for an answer)
        self.s.settimeout(0.0)
        self.sendCommand(None)

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
                self._streamReader(d)

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

"""
Chat class commonly used for event OnChat
"""
class ChatMessage():
    def __init__(self, channel, sender, message):
        self.channel = channel.lower()
        self.sender = sender
        self.message = message
