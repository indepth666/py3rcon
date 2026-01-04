import socket
import os
import sys
import binascii
import time
import datetime
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

        # last timestamp used for checking keepalive
        self.isExit = False
        self.isAuthenticated = False
        self.retry = 0
        self.exit_event = threading.Event()

        self.lastcmd = ""
        self.lastcmd_lock = threading.Lock()

        # Store last known player list for operations like kickAll
        self.current_players = []
        self.players_lock = threading.Lock()

        # Command pipeline with sequence numbers
        self.seq_number = 0
        self.seq_lock = threading.Lock()
        self.pending_commands = {}  # seq_number -> {'cmd': str, 'sent_at': time, 'retries': int}
        self.pending_lock = threading.Lock()
        self.command_timeout = 5.0  # seconds
        self.max_retries = 3

        # server message receive filters
        self.receiveFilter = [
            # receive all players
            (r"\n(\d+)\s+(.*?)\s+([0-9]+)\s+([A-z0-9]{32})\(.*?\)\s(.*)", self.__players, True),
            # receive missions
            (r"\n(.*\.[A-z0-9_-]+\.pbo)", self.__missions, True),
            # when player is connected
            (r"Verified GUID \(([A-Fa-f0-9]+)\) of player #([0-9]+) (.*)", self.__playerConnect, False),
            # when player is disconnected
            (r"Player #([0-9]+) (.*?) disconnected", self.__playerDisconnect, False),
            # chat messages
            (r"\((\w+)\) (.*?): (.*)", self.__chatMessage, False),
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
        while not self.isExit:
            time.sleep(self.KeepAlive)
            if not self.isExit:
                self.sendCommand(None, track=False)

    """
    private: threaded method to monitor pending commands and handle retransmissions
    """
    def _retryThread(self):
        while not self.isExit:
            time.sleep(1.0)  # Check every second

            if self.isExit:
                break

            current_time = time.time()
            commands_to_retry = []
            commands_to_drop = []

            # Check for timed out commands
            with self.pending_lock:
                for seq, cmd_info in list(self.pending_commands.items()):
                    age = current_time - cmd_info['sent_at']

                    if age > self.command_timeout:
                        if cmd_info['retries'] < self.max_retries:
                            # Retry this command
                            commands_to_retry.append((seq, cmd_info))
                            cmd_info['sent_at'] = current_time
                            cmd_info['retries'] += 1
                        else:
                            # Max retries reached, drop it
                            commands_to_drop.append(seq)

            # Retransmit timed out commands
            for seq, cmd_info in commands_to_retry:
                logging.warning('Retransmitting seq {} (retry {}/{}): "{}"'.format(
                    seq, cmd_info['retries'], self.max_retries, cmd_info['cmd']))
                # Resend with same sequence number
                self._resendCommand(seq, cmd_info['cmd'])

            # Drop commands that exceeded max retries
            with self.pending_lock:
                for seq in commands_to_drop:
                    cmd_info = self.pending_commands.pop(seq, None)
                    if cmd_info:
                        logging.error('Command failed after {} retries (seq {}): "{}"'.format(
                            self.max_retries, seq, cmd_info['cmd']))

    """
    private: resend a command with a specific sequence number
    """
    def _resendCommand(self, seq, cmd_str):
        if not self.isAuthenticated:
            return

        command = bytearray()
        command.append(0xFF)
        command.append(0x01)
        command.append(seq)
        command.extend(cmd_str.encode('utf-8','replace'))

        request = bytearray(b'BE')
        request.extend(self.__compute_crc(command))
        request.extend(command)

        self.s.sendto(request, (self.ip, self.port))

    """
    private: to calculate the crc (Battleye).
    More Info: http://www.battleye.com/downloads/BERConProtocol.txt
    """
    def __compute_crc(self, Bytes):
        crc = binascii.crc32(Bytes) & 0xffffffff
        return (
            (crc >> 0) & 0xFF,
            (crc >> 8) & 0xFF,
            (crc >> 16) & 0xFF,
            (crc >> 24) & 0xFF
        )

    """
    private: get next sequence number (0-255, wraps around)
    """
    def _get_next_seq(self):
        with self.seq_lock:
            seq = self.seq_number
            self.seq_number = (self.seq_number + 1) % 256
            return seq

    """
    public: send individual server commands.
    @param string toSendCommand - any valid server command, like "#ban <playerid>"
    @param bool track - whether to track this command for ACK (default True)
    @return int - sequence number used
    """
    def sendCommand(self, toSendCommand, track=True):
        if not self.isAuthenticated:
            logging.error('Command failed - Not Authenticated')
            return None

        # Get sequence number
        seq = self._get_next_seq()

        # request =  "B" + "E" + 4 bytes crc check + command
        command = bytearray()
        command.append(0xFF)
        command.append(0x01)
        command.append(seq)  # Use actual sequence number instead of 0x00

        if toSendCommand:
            logging.debug('Sending command "{}" with seq {}'.format(toSendCommand, seq))
            command.extend(toSendCommand.encode('utf-8','replace'))
        else:
            logging.debug('Sending keepAlive package with seq {}'.format(seq))

        # Track command in pending queue if requested
        if track and toSendCommand:
            with self.pending_lock:
                self.pending_commands[seq] = {
                    'cmd': toSendCommand,
                    'sent_at': time.time(),
                    'retries': 0
                }

        with self.lastcmd_lock:
            self.lastcmd = toSendCommand

        request = bytearray(b'BE')
        request.extend( self.__compute_crc(command) )
        request.extend(command)

        self.s.sendto(request ,(self.ip, self.port))
        return seq

    """
    public: send multiple commands in pipeline (fast batch processing)
    @param list commands - List of command strings to send
    @param float delay_between - Small delay between sends to avoid overwhelming server (default 0.001s)
    @param float timeout - Max time to wait for all ACKs (default 10s)
    @return dict - {'sent': int, 'acked': int, 'failed': list}
    """
    def sendBatch(self, commands, delay_between=0.001, timeout=10.0):
        if not self.isAuthenticated:
            logging.error('Batch commands failed - Not Authenticated')
            return {'sent': 0, 'acked': 0, 'failed': []}

        if not commands:
            return {'sent': 0, 'acked': 0, 'failed': []}

        logging.info('Sending batch of {} commands'.format(len(commands)))

        # Send all commands and track their sequence numbers
        seq_list = []
        start_time = time.time()

        for cmd in commands:
            if self.isExit:
                break

            seq = self.sendCommand(cmd, track=True)
            if seq is not None:
                seq_list.append(seq)

            # Small delay to avoid overwhelming the server
            if delay_between > 0:
                time.sleep(delay_between)

        sent_count = len(seq_list)
        logging.info('Batch sent: {} commands in {:.3f}s'.format(sent_count, time.time() - start_time))

        # Wait for all ACKs with timeout
        wait_start = time.time()
        failed_seqs = []

        while (time.time() - wait_start) < timeout:
            with self.pending_lock:
                # Check which commands are still pending
                pending_seqs = [seq for seq in seq_list if seq in self.pending_commands]

            if not pending_seqs:
                # All commands acknowledged!
                elapsed = time.time() - start_time
                logging.info('Batch completed: {}/{} ACKed in {:.3f}s'.format(sent_count, sent_count, elapsed))
                return {'sent': sent_count, 'acked': sent_count, 'failed': []}

            # Small sleep to avoid busy waiting
            time.sleep(0.01)

        # Timeout reached - check what's still pending
        with self.pending_lock:
            for seq in seq_list:
                if seq in self.pending_commands:
                    failed_seqs.append(seq)
                    cmd_info = self.pending_commands[seq]
                    logging.warning('Command timeout: seq {} - "{}"'.format(seq, cmd_info['cmd']))

        acked_count = sent_count - len(failed_seqs)
        elapsed = time.time() - start_time
        logging.warning('Batch timeout: {}/{} ACKed, {} failed in {:.3f}s'.format(
            acked_count, sent_count, len(failed_seqs), elapsed))

        return {'sent': sent_count, 'acked': acked_count, 'failed': failed_seqs}

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
        # reset the retries if from now on some connection problems occurred
        self.retry = 0

        #ACKNOWLEDGE THE MESSAGE
        p = packet[0]
        try:
            if p[0:2] == b'BE' and self.isAuthenticated:
                self.s.sendto(self._acknowledge(p[8:9]), (self.ip, self.port))

        except (IndexError, socket.error) as e:
            logging.debug('Failed to send acknowledgement: {}'.format(e))
        
        # Debug output the complete packet received from server
        logging.debug("[Server: %s:%s]: %s" % (self.ip, self.port, packet))

        stream = packet[0]

        # successfully authenticated packet received
        if stream[6:] == b'\xff\x00\x01':
            self.s.settimeout( self.Timeout )
            # Only do the below if this is the initial connect call
            if not self.isAuthenticated:
                self.isAuthenticated = True
                logging.info("Successfully connected and authenticated to {}:{}".format(self.ip, self.port))
                print("Connected to RCON server {}:{}".format(self.ip, self.port))
                self.OnConnected()
            else:
                logging.info("Reconnected to {}:{}".format(self.ip, self.port))
                print("Reconnected to RCON server")
                self.OnReconnected()
            return
        # when authentication failed, exit the program
        if stream[6:] == b'\xff\x00\x00':
            logging.error("Authentication FAILED - Wrong password for {}:{}".format(self.ip, self.port))
            print("ERROR: Authentication FAILED - Wrong RCON password!")
            print("Check your password in the config file")
            exit()
        
        # Handle ACK for commands (0xFF 0x01 = command response)
        if stream[6:8] == b'\xff\x01':
            # Extract sequence number from ACK
            if len(stream) > 8:
                ack_seq = stream[8]
                logging.debug('Received ACK for seq {}'.format(ack_seq))

                # Remove from pending commands
                with self.pending_lock:
                    if ack_seq in self.pending_commands:
                        cmd_info = self.pending_commands.pop(ack_seq)
                        logging.info("[Server: %s:%s]: ACK seq %d - '%s'" % (self.ip, self.port, ack_seq, cmd_info['cmd']))
                    else:
                        logging.debug('ACK for seq {} (not tracked or already removed)'.format(ack_seq))

            # Legacy lastcmd handling for backwards compatibility
            with self.lastcmd_lock:
                if self.lastcmd:
                    logging.debug('Command completed: {}'.format(self.lastcmd))
                else:
                    logging.info("[Server: %s:%s]: KeepAlive ACK" % (self.ip, self.port))
        # all other packages and commands
        if len(stream[9:]) > 0:
            stream = stream[9:].decode('utf-8', 'replace')
            self.__parseResponse(stream)

            logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, stream))

    def __players(self, pl):
        l = []
        for m in pl:
            l.append( Player(m[0], m[3], m[4]) )

        with self.players_lock:
            self.current_players = l

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
    public: kick all players (using batch pipeline for speed)
    """
    def kickAll(self):
        logging.info('Kick All players before restart')

        with self.players_lock:
            players_to_kick = list(self.current_players)

        if not players_to_kick:
            logging.warning('No players in current player list, requesting player list first')
            self.sendCommand('players', track=False)
            time.sleep(0.5)  # Wait for response
            with self.players_lock:
                players_to_kick = list(self.current_players)

        if not players_to_kick:
            logging.info('No players to kick')
            return {'sent': 0, 'acked': 0, 'failed': []}

        # Build batch of kick commands
        kick_commands = ['kick {}'.format(player.number) for player in players_to_kick]
        logging.info('Kicking {} players using pipeline: {}'.format(
            len(players_to_kick),
            ', '.join([p.name for p in players_to_kick])
        ))

        # Send all kicks in pipeline (much faster than sequential)
        result = self.sendBatch(kick_commands, delay_between=0.005, timeout=5.0)

        if result['failed']:
            logging.warning('Failed to kick {} players'.format(len(result['failed'])))

        return result

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
        _t = threading.Thread(target=self._keepAliveThread, name='keepAliveThread')
        _t.daemon = True
        _t.start()

        # initialize retry/timeout thread
        _r = threading.Thread(target=self._retryThread, name='retryThread')
        _r.daemon = True
        _r.start()

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
        self.exit_event.set()
        self.OnAbort()
        try:
            self.s.close()
            logging.debug("Socket closed")
        except Exception as e:
            logging.debug("Error closing socket: {}".format(e))

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

            if self.retry == 0:
                logging.info('Attempting to connect to RCON server {}:{}'.format(self.ip, self.port))
                print('Connecting to {}:{}...'.format(self.ip, self.port))
            else:
                logging.info('Connecting to {}:{} (retry #{})'.format(self.ip, self.port, self.retry))

            self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))

            # receive data from client (data, addr)
            while not self.isExit:
                d = self.s.recvfrom(4096)           # Increased from 2048 to handle larger responses
                self.__streamReader(d)

        # Connection timed out
        except socket.timeout as et:
            if self.retry < self.ConnectionRetries and not self.isExit:
                self.retry += 1
                logging.warning('Connection timeout (attempt {}/{}): {} - Retrying in {}s...'.format(
                    self.retry, self.ConnectionRetries, et, self.ConnectionInterval))
                print('WARNING: Connection timeout (attempt {}/{}) - Retrying...'.format(
                    self.retry, self.ConnectionRetries))
                self.connect()
            else:
                logging.error('Connection failed after {} retries: {}'.format(self.ConnectionRetries, et))
                print('ERROR: Connection FAILED - Cannot reach RCON server at {}:{}'.format(self.ip, self.port))
                print('Make sure:')
                print('  1. The server is running')
                print('  2. RCON is enabled on port {}'.format(self.port))
                print('  3. The password is correct')
                self.Abort()

        # Some problem sending data ??
        except socket.error as e:
            logging.error('Socket error: {}'.format(e))
            self.Abort()

        # Ctrl + C
        except (KeyboardInterrupt, SystemExit):
            logging.debug('rconprotocol.connect: Keyboard interrupted')
            self.Abort()

        except Exception:
            logging.exception("Unhandled Exception in connect()")
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
