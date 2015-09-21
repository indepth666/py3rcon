import socket
import os
import sys
import binascii
import time, datetime
import threading
import sched
import logging

class RestartMessage():

    def __init__(self, min, message):
        self.min = min
        self.message = message

    def toSecond(self):
	return self.min * 60

class Rcon():

    Timeout = 60 # When the connection did not received any response after this period
    KeepAlive = 40 # KeepAlive must always be lower than Timeout, otherwise the Timeout occurs
    ConnectionRetries = 6 # Try to reconnect (at startup) X times and...
    ConnectionInterval = 10 # ... try it every 10 seconds. Example (6 tries X 10 seconds = 60 seconds until server should be up)

    def __init__(self, ip, password, Port, streamWriter=True, exitOnRestart=False):
	# constructor parameters
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter

	# last timestamp used for checkinh keepalive
	self.exitOnRestart = exitOnRestart
	self.isExit = False
	self.isAuthenticated = False
	self.retry = 0
	self.lastcmd = ""

	# shutdown and shutdown message scheduler
	self.sched = sched.scheduler(time.time, time.sleep)
	self.shutdownTimer = 0
	self.restartMessages = None

	# chat messages
	self.repeatMessages = None
	self.repeatMessageInterval = 0
	self.repeatMessageIndex = 0

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as serr:
            print ('Failed to create socket')
	    logging.error('rconprotocol: Failed to created socket: {}'.format(serr))
            sys.exit()

    def _messageLoop(self):
	logging.info('Message loop thread initialized')

	_counter = 0;
        while not self.isExit:
	    time.sleep(1)
	    _counter += 1
	
	    # when counter hits KeepAlive interval, call _sendKeepAlive
	    if _counter%self.KeepAlive == 0:
		self._sendKeepAlive()

	    # check every repeatMessageInterval if chat message need to be sent
	    if self.repeatMessageInterval > 0 and _counter%self.repeatMessageInterval == 0:
		t = threading.Thread(target=self._sendSequentialMessageThread, args=())
		t.daemon = True
		t.start()
	    
	    # not neccessary need, but to have it porperly
	    if _counter > 0xffffffff:
		_counter = 0

    def _compute_crc(self, Bytes):
        buf = memoryview(Bytes)
        crc = binascii.crc32(buf) & 0xffffffff
        crc32 = '0x%08x' % crc
        return int(crc32[8:10], 16), int(crc32[6:8], 16), int(crc32[4:6], 16), int(crc32[2:4], 16)

    def _sendKeepAlive(self):
	self.sendCommand(None)

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

	# Connection timed out
	#except socket.timeout as et:
	#    logging.error('Socket timeout: {}'.format(et))

        # Some problem sending data ??
        #except socket.error as e:
	#    logging.error('Socket error: {}'.format(e))

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
		    self._initThreads()
	    # when authentication failed, exit the program
	    elif stream[6:] == "\xff\x00\x00":
		logging.error("Not Authenticated")
		exit()
	    # keepAlive package received
	    elif stream[6:] == "\xff\x01\x00" and self.lastcmd:
		stream = "ACK {}".format(self.lastcmd)
	    elif stream[6:] == "\xff\x01\x00" and not self.lastcmd:
        	stream = "KeepAlive"
	    # all other packages and commands
	    else:
		stream = stream[9:].decode('ascii', 'replace')

	    logging.info("[Server: %s:%s]: %s" % (self.ip, self.port, stream))
	    logging.debug("[Server: %s:%s]: %s" % (self.ip, self.port, packet))

            split = stream.split(' ')

            #Write GUID&NAME
            if len(split) > 6:
                if split[0] == "Verified" and \
                    split[1] == "GUID" and \
                    split[3] == "of":
                    guid = split[2]
                    playername =  split[6:]
                    pname = str.join(" ", playername)
		    logging.info('Player {} with Guid: {}'.format(pname, guid[1:-1]))

    
    def _sendSequentialMessageThread(self):
	_l = len(self.repeatMessages)
	_index = self.repeatMessageIndex
	if _l > 0 and not self.repeatMessages[_index] == None:
	    self.sendChat(self.repeatMessages[_index])
	
	if (_index + 1) >= _l:
	    self.repeatMessageIndex = 0
	else:
	    self.repeatMessageIndex += 1

    def sendChat(self, msg):
	self.sendCommand("say -1 \"%s\"" % msg)

    def messengers(self, messagesAsList, timeBetweenMessage=10, beginWith = 0):
	self.repeatMessages = messagesAsList
	self.repeatMessageInterval = timeBetweenMessage * 60;
	self.repeatMessageIndex = beginWith

    def _restartMessageTask(self, msg):
	logging.info('Sending restart message: {}'.format(msg))
	self.sendCommand("say -1 \"%s\"" % msg)
	
    def kickAll(self):
	logging.info('Kick All player before restart take action')
	for i in range(1, 100):
	    self.sendCommand('#kick {}'.format(i))
	    time.sleep(0.1)

    def lockServer(self):
	self.sendCommand('#lock')
	time.sleep(1)

    def _shutdownTask(self):
	self.lockServer();
	self.kickAll()

	# wait some seconds before restarting
	logging.info('Delay the shutdown process')
	time.sleep(30)
	
	logging.info('Sending shutdown command')
	self.sendCommand('#shutdown')

    def _emptyScheduler(self):
	if not self.sched.empty():
	    for q in self.sched.queue:
	        self.sched.cancel(q)

    def _initRestartScheduler(self):
	logging.info('Initialized the restarter thread')
	
	# make sure all previous scheds are being removed
	self._emptyScheduler()
	self.sched.enter(self.shutdownTimer, 1, self._shutdownTask, ())

	if type(self.restartMessages) is list:
    	    for msg in self.restartMessages:
		if int(self.shutdownTimer - msg.toSecond()) > 0:
		    self.sched.enter( self.shutdownTimer - msg.toSecond(), 1, self._restartMessageTask, (msg.message,) )
	
	self.sched.run()
	logging.debug('All shutdown tasks executed')
	if self.exitOnRestart:
	    logging.info('Exit Pyrcon...')
	    self.isExit = True

    def shutdown(self, shutdownInterval, restartMessageAsList):
	self.shutdownTimer = shutdownInterval * 60
	self.restartMessages = restartMessageAsList

    def _initThreads(self):
	# a message loop to handle keepAlive, connection timeouts and global chat messages
        t = threading.Thread(target=self._messageLoop)
	t.daemon = True
    	t.start()

	# a separate thread to handle the restart and restart messages
	# It is set as daemon to be able to stop it using SystemExit or Ctrl + C
	t = threading.Thread(target=self._initRestartScheduler)
	t.daemon = True
	t.start()

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
	    if self.retry < self.ConnectionRetries:
		self.retry += 1
		self.connect()

        # Some problem sending data ??
        except socket.error as e:
	    logging.error('Socket error: {}'.format(e))

        # Ctrl + C
        except (KeyboardInterrupt, SystemExit):
	    logging.debug('rconprotocol.connect: Keyboard interrupted')
