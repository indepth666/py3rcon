pythonBERCon
============

PythonBERCon is a Python3 client for Battleye Rcon protocol. 
It's designed with ARMA2 and ARMA3 in mind but may also work with other implemenation of the protocol.


How to use?
===========

Configuration example can be found in configexample.json.
then ./pyrcon.py configfile

Configuration explained
=======================

Please note the configuration is stored JSON file.
This format usually does not allow comments.


**logfile: "pyrcon.log"** - Logfile name
**loglevel: 10** - Loglevel (10 = show debug info, 20 = show info messages, 30 = show error and warnings only)

**server -> host: "<ip address/hostname>"** - Ip address of the armaX server
**server -> port: "<port>"** - Ip address of the armaX server
**server -> rcon_password: "<pw>"** - Rcon password

**restart -> interval: <minutes>** - Restart interval in minutes
**restart -> exitonrestart: <booloean>** - Exit the application when restart interval has reached

