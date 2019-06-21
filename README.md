# zabbix-rhds
Red Hat Directory Server monitoirng with Zabbix

# Support
This program and related components are not officially supported or maintained by Red Hat.

## Description
Red Hat Directory Server monitoring with ldap.


## Requirements
* python-ldap
* python-dateutil

## Installation
To configure the utilities copy the `config.yaml-default` to `config.yaml` and edit with the appropriate information.  Often all you will need to change is the user name to connect with, the password and the url to connect to.

To install copy the files `get_data.py`, `get_discovery.py` and `config.yaml` into a directory of your choosing, often the zabbix user home directory (/var/lib/zabbix).

Copy the `userparameter_rhds.conf` file to `/etc/zabbix/zabbix_agentd.d` and ensure that the zabbix agent configuration file references this directory.  If you installed the scripts into a directory other than /var/lib/zabbix you will need to edit this file with the correct path.

Restart the agent as needed.

To test run:
`zabbix_agentd -t get_data`
If successful you should see a large chunk of JSON formatted data, if not the error messages should give you a starting point.

## SELinux
Unfortunately at this time SELinux cannot be set to enforcing with out first creating a custom module on RHEL 7.  It is recommended to either use Permissive mode for now, or to create your own custom SELinux module.


## A special thank you
I would like to specifically thank Richard Megginson (github: richm) for his intricate work on Replication montoring.  The replication monitoring portions of these scripts were reverse engineered from his efforts.