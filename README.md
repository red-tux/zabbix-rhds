# zabbix-rhds
Red Hat Directory Server monitoirng with Zabbix

# License
This software is released under the GPL V3 Open Source Licence.

# Support
This program and related components are not officially supported or maintained by Red Hat.

## Description
Red Hat Directory Server monitoring with ldap.


## Requirements
The following RPMS are required on RHEL
* python-ldap
* python-dateutil


## Installation
### Installing the scripts
After installing the above required dependencies, copy the .py files to the zabbix user's home directory.  When using the Zabbix SIA RPMs this is /var/lib/zabbix.  You may need to create this directory, if you do ensure it is owned by Zabbix and the SElinux contexts are set appropriately.

Next copy the `config.yaml-default` to `config.yaml` in the Zabbix user's home directory and edit with the appropriate information.  Often all you will need to change is the user name to connect with, the password and the url to connect to.

**NOTE:  It is important that the `url` statement be correct on each host being configured to monitor.  Otherwise all hosts may connect to the wrong initial host for data.**

For replication monitoring the user listed in the config file will be used to connect to each host.  Right now there is no way to specify a different username/password for each host.  Replication monitoring requires that the script running on host A be able to connet to each host it has a replication agreement with to check the RUV (Replication Update Vector) on each host to ensure they are in sync.

You can test that everything works by executing `get_data.py` or `get_replication.py` from the command line.  It is suggested that you execute the scripts as Zabbix if you are able as each python file will be compiled at execution, in addition this ensures better testing of SELinux and other security frameworkds which may prevent the scripts from properly running.  Upon proper execution you should see a large set of JSON formatted data on screen.  

### Configuring the Zabbix agent
NOTE: This guide assumes you are using includes for the Zabbix agent configuration, for more information see: https://www.zabbix.com/documentation/4.2/manual/appendix/config/zabbix_agentd

Copy the `userparameter_rhds.conf` file to the `/etc/zabbix/zabbix_agent.d/`.  The file does not need to be owned by Zabbix, but must be readable by it.

To test the userparameter you can execute the following on the command line `zabbix-agentd -t ldap_stats`.  You should see a large set of JSON data on screen similar to what you would see if you executed `get_data.py`

### Configuring Zabbix
Next import the `Template RHDSLDAP.xml` file into Zabbix and associate to all LDAP servers.

By default replication will auto-discover once an hour.  This can be altered as needed, or run manually (preferable).  However after a replication auto-discovery is run all items will not populate until the next replication data check (key: `ldap_replication`)

## Ldap Permissions
If you choose to create your own user and ACI for monitoring (recommended) the following DN's are queried for all objectclasses unless otherwise noted:
* cn=features, cn=config
* cn=monitor, cn=config
* cn=snmp, cn=config
* cn=replication, cn=config
* cn=monitor
* cn=mapping tree, cn=config
  * Full SubTree
  * objectclasses:
    * nsDS5ReplicationAgreement
    * nstombstone

## SELinux
Unfortunately at this time SELinux cannot be set to enforcing with out first creating a custom module on RHEL 7.  It is recommended to either use Permissive mode for now, or to create your own custom SELinux module.

## Sample output
The following are sample outputs of the LDAP monitoring and Replicaiton monitoring data:
* [get_data.py](https://gist.github.com/red-tux/34aad1587937e88e88b0f8806edf1639)
* [get_replication.py](https://gist.github.com/red-tux/630d8d54eddfc104c02ef18dd2deaa88)

## A special thank you
I would like to specifically thank Richard Megginson (github: richm) for his intricate work on Replication montoring.  The replication monitoring portions of these scripts were reverse engineered from his efforts.