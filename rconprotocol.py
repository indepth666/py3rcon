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

    Timeout = 60
    KeepAlive = 40
    AutoReconnect = 70

    def __init__(self, ip,password,Port,streamWriter=True):
	self.sched = sched.scheduler(time.time, time.sleep)
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter
        self.lastMessageTimer = 0
        self.messagesTimer = 10 * 60                        #USED BY THE MESSENGER

	self.shutdownTimer = 0
	self.restartMessages = None
	self.hasRestarted = 1

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            print ('Failed to create socket')
            sys.exit()

    def _secondsCounter(self):
        while True:
            time.sleep(1)
            self.lastMessageTimer += 1
            if self.lastMessageTimer > self.Timeout:
                print "[Server: {}:{}] [WARNING]: No message received for {} seconds - Try to reconnect shortly".format(self.ip,self.port, self.lastMessageTimer)
            if self.lastMessageTimer > self.AutoReconnect:
                print "[WARNING]: Last message received {} seconds ago. Reconnecting!".format(self.AutoReconnect)
                self.lastMessageTimer = 0
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))
		self._initRestartScheduler()

    def _compute_crc(self, Bytes):
        buf = memoryview(Bytes)
        crc = binascii.crc32(buf) & 0xffffffff
        crc32 = '0x%08x' % crc
        return int(crc32[8:10], 16), int(crc32[6:8], 16), int(crc32[4:6], 16), int(crc32[2:4], 16)

    def _keepAlive(self):
        while True:
            time.sleep(self.KeepAlive)
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
        self.lastMessageTimer = 0
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
            streamWithTime = "[Server: %s:%s] [%s:%s:%s]: %s" % (self.ip, self.port, a.hour, a.minute, a.second, stream)
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

    def _messengerThread(self,rtime,messageList):
        print "NOTE: Initialized the Messenger thread\n"
        while True:
            for i in range(0,len(messageList)):
                self.sendCommand("say -1 \"%s\"" % messageList[i])
                time.sleep(rtime)

    def messengers(self, messagesAsList, timeBetweenMessage=10):
        rtime = timeBetweenMessage * 60
        t = threading.Thread(target=self._messengerThread, args=(rtime, messagesAsList))
	t.daemon = True
        t.start()

    def _restartMessageTask(self, msg):
	print 'Sending Restart Message: %s' % msg
	self.sendCommand("say -1 \"%s\"" % msg)
	



    def kickAll(self):
	print 'Kick All players executed'
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
	time.sleep(30)

	self.sendCommand('#shutdown')

	self.hasRestarted = 1
	#self.sendCommand('players')

    def _initRestartScheduler(self):
	if self.hasRestarted == 1:
	
	    print 'NOTE: Initialized the Restarter thread'

	    if not self.sched.empty():
		for q in self.sched.queue:
		    self.sched.cancel(q)

	    self.sched.enter(self.shutdownTimer, 1, self._shutdownTask, ())

	    self.hasRestarted = 0

	    if type(self.restartMessages) is list:
        	for msg in self.restartMessages:
		    if int(self.shutdownTimer - msg.toSecond()) > 0:
			self.sched.enter( self.shutdownTimer - msg.toSecond(), 1, self._restartMessageTask, (msg.message,) )

	    self.sched.run()

    def shutdown(self, shutdownInterval, restartMessageAsList):
	rtime = shutdownInterval * 60
	self.shutdownTimer = rtime
	self.restartMessages = restartMessageAsList

	threading.Thread(target=self._initRestartScheduler).start();

    def connect(self):
        while(1):
            try :
                #msg = input('Enter message to send : ')
                #Set the whole string
                print("Connected loop (Normal behavior)\n")
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))

                # send keep alive package every X seconds
                t = threading.Thread(target=self._keepAlive)
		t.daemon = True
                t.start()

                secondTimer = threading.Thread(target=self._secondsCounter)
		secondTimer.daemon = True
                secondTimer.start()

                # receive data from client (data, addr)
                #time.sleep(3)
                while True:
                    d = self.s.recvfrom(2048)           #1024 value crash on players request on full server
                    self._streamReader(d)

                break

            # Some problem sending data ??
            except socket.error as e:
                #pass
                print('Error... Disconnection? ' + str(e[0]) + ' Message ' + e[1])
                #print ('Error Code : ' + str(e[0]) + ' Message ' + e[1])
                #sys.exit()

            # Ctrl + C
            except (KeyboardInterrupt, SystemExit):
                break
