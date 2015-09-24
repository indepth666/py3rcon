pythonBERCon
============

PythonBERCon is a Python3 client for Battleye Rcon protocol. 
It's designed with ARMA2 and ARMA3 in mind but may also work with other implemenation of the protocol.


How to use?
===========

Configuration example can be found in configexample.json.

<pre>Usage: ./pyrcon.py &lt;configfile&gt;</pre>

Configuration explained
=======================

Please note the configuration is stored JSON file.
This format usually does not allow comments.

Config entry          | Example       | Description
--------------------- | ------------- | -----------
logfile               | pyrcon.log    | File name of the pyrcon log
loglevel              | 10            | Loglevel (10 = show debug info, 20 = exclude debug info, 30 = display only error and warnings)
server : host         | 127.0.0.1     | Hostname of the armaX server
server : port         | 2402          | Port of the armaX server
server : rcon_password| yourPW        | Rcon password
restart : interval    | 240           | Restart interval in minutes
restart : exitonrestart| true         | End the application when restart interval has reached

