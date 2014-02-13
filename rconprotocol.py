import socket
import sys
import binascii
import time, datetime
import threading


class Rcon():

    def __init__(self, ip,password,Port,streamWriter=True):
        self.ip = ip
        self.password = password
        self.port = int(Port)
        self.writeConsole = streamWriter

        self.lastMessageTimer = 0


        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            print ('Failed to create socket')
            sys.exit()

    def _secondsCounter(self):
        while True:
            time.sleep(1)
            self.lastMessageTimer += 1
            if self.lastMessageTimer > 90:
                print("[WARNING]: No message received for ", str(self.lastMessageTimer), " seconds, will try to reconnect at 120seconds")
            if self.lastMessageTimer > 120:
                print("[WARNING]: Last message received 120 seconds ago... -> Reconnecting")
                self.lastMessageTimer = 0
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))


    def _compute_crc(self, Bytes):
        buf = memoryview(Bytes)
        crc = binascii.crc32(buf) & 0xffffffff
        crc32 = '0x%08x' % crc
        return int(crc32[8:10], 16), int(crc32[6:8], 16), int(crc32[4:6], 16), int(crc32[2:4], 16)

    def _noTimeout(self):
        while True:
            time.sleep(40)
            command = bytearray()
            command.append(0xFF)
            command.append(0x01)
            command.append(0x00)
            command.append(0x00)
            command.append(0x00)

            request = bytearray(b'BE')
            crc1, crc2, crc3, crc4 = self._compute_crc(command)
            request.append(crc1)
            request.append(crc2)
            request.append(crc3)
            request.append(crc4)
            request.extend(command)
            self.s.sendto(request ,(self.ip, self.port))
            #print("Just sent timeout empty packet\n")

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

        #return request

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
        #return request


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
            streamWithTime = "[%s:%s:%s]: %s" % (a.hour, a.minute, a.second, stream)
            print(streamWithTime)




    def connect(self):
        while(1):
            try :
                #msg = input('Enter message to send : ')
                #Set the whole string
                print("Connected loop (Normal behavior)\n")
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))


                #prevent disconnection
                t = threading.Thread(target=self._noTimeout)
                t.start()

                secondTimer = threading.Thread(target=self._secondsCounter)
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
            except KeyboardInterrupt:
                break


