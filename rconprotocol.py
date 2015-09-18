import socket
import sys
import binascii
import time, datetime
import threading
import sched

class RestartMessage():

    def __init__(self, min, message):
        self.min = min
        self.message = message

    def toSecond(self):
	return self.min * 60

class Rcon():

    Timeout = 45
    AutoReconnect = 50
    KeepAlive = 40

    def __init__(self, ip, password, Port, streamWriter=True):
	# constructor parameters
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter

	# last timestamp used for checkinh keepalive
	self.IsAlive = 0

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
        except socket.error:
            print ('Failed to create socket')
            sys.exit()

    def _messageLoop(self):
	print("NOTE: Message loop thread initialized\n")

	_counter = 0;
        while True:
	    time.sleep(1)
	    _counter += 1
	    # when counter hits KeepAlive interval, call _sendKeepAlive
	    if _counter%self.KeepAlive == 0:
		self._sendKeepAlive()

	    # check every repeatMessageInterval if chat message need to be sent
	    if self.repeatMessageInterval > 0 and _counter%self.repeatMessageInterval == 0:
		t = threading.Thread(target=self._sendSequentialMessageThread, args=()).start()
	    
	    # when Timeout is reached (and keepalive did not received any reply), show warning
	    if self.IsAlive > 0 and int(time.time() - self.IsAlive) > self.Timeout:
		print "[Server: {}:{}] [WARNING]: No message received for {} seconds - Try to reconnect shortly".format(self.ip,self.port, int(time.time() - self.IsAlive))
	
	    # when autoconnect time has reached, than try to reconnect
	    if int(time.time() - self.IsAlive) > self.AutoReconnect:
		print "[WARNING]: Last message received {} seconds ago. Reconnecting!".format( int(time.time() - self.IsAlive) )
		self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))
		t = threading.Thread(target=self._initRestartScheduler)
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
        command = bytearray()
        command.append(0xFF)
        command.append(0x01)
        command.append(0x00)

        request = bytearray(b'BE')
        crc1, crc2, crc3, crc4 = self._compute_crc(command)
        request.append(crc1)
        request.append(crc2)
        request.append(crc3)
        request.append(crc4)
        request.extend(command)
        self.s.sendto(request ,(self.ip, self.port))

    def sendCommand(self, toSendCommand):
        # request =  "B" + "E" + 4 bytes crc check + command

        command = bytearray()
        command.append(0xFF)
        command.append(0x01)
        command.append(0x00)       #sequence number, must be incremented
        command.extend(toSendCommand.encode('utf-8','replace'))

        request = bytearray(b'BE')
        crc1, crc2, crc3, crc4 = self._compute_crc(command)
        request.append(crc1)
        request.append(crc2)
        request.append(crc3)
        request.append(crc4)
        request.extend(command)
        try:
            self.s.sendto(request ,(self.ip, self.port))
        except:
            print("Error occured with Rcon.sendCommand")

    def _sendLogin(self, passwd):
        # request =  "B" + "E" + 4 bytes crc check + command
        time.sleep(1)
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
        #ACKNOWLEDGE THE MESSAGE
	# update the alive status
	self.IsAlive = time.time()

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
            stream = stream[9:].decode('ascii', 'replace')
            streamWithTime = "[Server: %s:%s] [%s]: %s" % (self.ip, self.port, a.strftime('%Y-%m-%d %H:%M:%S') , stream)
            print(streamWithTime)

            split = stream.split(' ')

            #Write GUID&NAME
            if len(split) > 6:
                if split[0] == "Verified" and \
                    split[1] == "GUID" and \
                    split[3] == "of":
                    guid = split[2]
                    playername =  split[6:]
                    pname = str.join(" ", playername)
                    print("Player: ", pname, " Guid: ", guid[1:-1])

    
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
	print 'NOTE: Sending Restart Message: %s' % msg
	self.sendCommand("say -1 \"%s\"" % msg)
	
    def kickAll(self):
	print 'NOTE: Kick All players'
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
	print 'NOTE: Delay the shutdown process quite a bit'
	time.sleep(20)
	
	print 'NOTE: Sending shutdown command'
	self.sendCommand('#shutdown')

    def _emptyScheduler(self):
	if not self.sched.empty():
	    for q in self.sched.queue:
	        self.sched.cancel(q)

    def _initRestartScheduler(self):
	print 'NOTE: Initialized the Restarter thread'
	
	# make sure all previous scheds are being removed
	self._emptyScheduler()
	self.sched.enter(self.shutdownTimer, 1, self._shutdownTask, ())

	if type(self.restartMessages) is list:
    	    for msg in self.restartMessages:
		if int(self.shutdownTimer - msg.toSecond()) > 0:
		    self.sched.enter( self.shutdownTimer - msg.toSecond(), 1, self._restartMessageTask, (msg.message,) )
	
	self.sched.run()

    def shutdown(self, shutdownInterval, restartMessageAsList):
	self.shutdownTimer = shutdownInterval * 60
	self.restartMessages = restartMessageAsList

	# a separate thread to handle the restart and restart messages
	# It is set as daemon to be able to stop it using SystemExit or Ctrl + C
	t = threading.Thread(target=self._initRestartScheduler)
	t.daemon = True
	t.start()

    def connect(self):
        while(1):
            try :
                #Set the whole string
		print 'NOTE: Connecting to {}:{}'.format(self.ip, self.port)
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))

                # a message loop to handle keepAlive, connection timeouts and global chat messages
                t = threading.Thread(target=self._messageLoop)
		t.daemon = True
                t.start()
	
                # receive data from client (data, addr)
                while True:
                    d = self.s.recvfrom(2048)           #1024 value crash on players request on full server
                    self._streamReader(d)

                break

            # Some problem sending data ??
            except socket.error as e:
                #pass
                print('Error... Disconnection? ' + str(e[0]) + ' Message ' + e[1])

            # Ctrl + C
            except (KeyboardInterrupt, SystemExit):
		print 'connect: interrupted'
                break
