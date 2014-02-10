pythonBERCon
============

Python3 Battleye Rcon protocol
This is a very early Battleye Rcon communication protocol coded in Python3



Exemple program that use the library.
```
import threading
import rconprotocol

password = "somepasswd"
host = '69.39.239.100'
port = 2302
rcon = rconprotocol.Rcon(host,password, port)

t = threading.Thread(target=rcon.connect)
t.start()
```
