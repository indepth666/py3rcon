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
        self.consolelog = streamWriter
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            print ('Failed to create socket')
            sys.exit()




    def _compute_crc(self, Bytes):
        buf = memoryview(Bytes)                     #used to be buf = memoryview(Bytes)
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
        # request =  "B" + "E" + chr(crc1) + chr(crc2) + chr(crc3) + chr(crc4) + command
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
        # request =  "B" + "E" + chr(crc1) + chr(crc2) + chr(crc3) + chr(crc4) + command
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
        #ACKNOWLEDGE THE MESSAGE:
        p = packet[0]
        try:
            if p[0:2] == b'BE':

                #print(p[8:9])
                self.s.sendto(self._acknowledge(p[8:9]), (self.ip, self.port))
        except:
            pass



        #READ THE STREAM
        if self.consolelog is True:

            a = datetime.datetime.now()

            stream = packet[0].decode('utf-8', 'ignore')
            streamlist = stream.split()                             #Split the steam to be able to remove first byte
            streamlist[0] = "[%s:%s:%s]: " % (a.hour, a.minute, a.second)                                    #Remove the first byte

            print(str.join(' ', streamlist))



    def connect(self, printStream=False):
        while(1):
            try :
                #msg = input('Enter message to send : ')
                #Set the whole string
                print("Connected loop (Normal behavior)\n")
                self.s.sendto(self._sendLogin(self.password) ,(self.ip, self.port))
                time.sleep(1)


                #prevent disconnection

                t = threading.Thread(target=self._noTimeout)
                t.start()

                # receive data from client (data, addr)
                #time.sleep(3)
                while True:
                    d = self.s.recvfrom(1024)
                    self._streamReader(d)
                    #time.sleep(1)
                break

            # Some problem sending data ??
            except socket.error as e:
                pass
                #print ('Error Code : ' + str(e[0]) + ' Message ' + e[1])
                #sys.exit()



            # Ctrl + C
            except KeyboardInterrupt:
                break


