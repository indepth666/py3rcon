import socket
import os
import sys
import binascii
import time, datetime
import threading
import logging

class Rcon():

    Timeout = 60 # When the connection did not received any response after this period
    KeepAlive = 40 # KeepAlive must always be lower than Timeout, otherwise the Timeout occurs
    ConnectionRetries = 6 # Try to reconnect (at startup) X times and...
    ConnectionInterval = 10 # ... try it every 10 seconds. Example (6 tries X 10 seconds = 60 seconds until server should be up)

    def __init__(self, ip, password, Port, streamWriter=True):
	# constructor parameters
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter

	# connection handler for modules
	self.handlerConnect = []

	# last timestamp used for checkinh keepalive
	self.isExit = False
	self.isAuthenticated = False
	self.retry = 0
	self.lastcmd = ""

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as serr:
            print ('Failed to create socket')
	    logging.error('rconprotocol: Failed to created socket: {}'.format(serr))
            sys.exit()

    def loadmodule(self, name, cls, optClasses = []):
	_lst = [cls] + optClasses

	mod = __import__('lib.' + name, fromlist=_lst)
	#mod = importlib.import_module('lib.' + name)

	classT = getattr(mod, cls);
	clsObj = classT(self)
	if "OnConnected" in dir(clsObj):
	    self.handlerConnect.append(clsObj.OnConnected)

	return clsObj

    def _keepAliveThread(self):
	_counter = 0
	while not self.isExit:
	    time.sleep(1)
	    _counter += 1
	    if _counter%self.KeepAlive == 0:
		self.sendCommand(None)

	    if _counter > self.KeepAlive:
		_counter = 0

    def _compute_crc(self, Bytes):
        buf = memoryview(Bytes)
        crc = binascii.crc32(buf) & 0xffffffff
        crc32 = '0x%08x' % crc
        return int(crc32[8:10], 16), int(crc32[6:8], 16), int(crc32[4:6], 16), int(crc32[2:4], 16)

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
		    self.OnConnected()
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


    def sendChat(self, msg):
	self.sendCommand("say -1 \"%s\"" % msg)

    def kickAll(self):
	logging.info('Kick All player before restart take action')
	for i in range(1, 100):
	    self.sendCommand('#kick {}'.format(i))
	    time.sleep(0.1)

    def lockServer(self):
	self.sendCommand('#lock')
	time.sleep(1)

    def OnConnected(self):
	# initialize keepAlive thread
	_t = threading.Thread(target=self._keepAliveThread)
	_t.deamon = True
	_t.start()
	
	if len(self.handlerConnect) > 0:
	    for conn in self.handlerConnect:
		conn()

    def IsAborted(self):
	return self.isExit

    def Abort(self):
	logging.info("Exit loop")
	self.isExit = True

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
