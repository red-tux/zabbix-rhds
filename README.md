# zabbix-rhds
Red Hat Directory Server monitoirng with Zabbix

## Description
Red Hat Directory Server monitoring with ldap.


## Requirements
* python-ldap
* python-dateutil

## Installation
To install copy the files into a directory of your choosing, often the zabbix user home directory (/var/lib/zabbix).  Next copy the config.py-default to config.py.  Then edit the config.py file with the appropriate information.

Copy the userparameter_rhds.conf file to /etc/zabbix/zabbix_agend.d and ensure that the zabbix agent configuration file references this directory.  Restart the agent as needed.



