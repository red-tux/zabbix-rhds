#!/usr/bin/env python

import sys
import json
import os
import stat
import time
import argparse
from get_data import *

key_map = {
  "ldap.bytessent_per_sec": "['cn=snmp,cn=monitor']['bytessent']",
  "ldap.entriesreturned_per_sec": "['cn=snmp,cn=monitor']['entriesreturned']",
  "ldap.errors": "['cn=snmp,cn=monitor']['errors']",
  "ldap.inops_per_sec": "['cn=snmp,cn=monitor']['inops']",
  "ldap.ldbm.currentdncachecount": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['currentdncachecount']",
  "ldap.ldbm.currentdncachesize": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['currentdncachesize']",
  "ldap.ldbm.currententrycachecount": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['currententrycachecount']",
  "ldap.ldbm.currententrycachesize": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['currententrycachesize']",
  "ldap.ldbm.maxdncachesize": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['maxdncachesize']",
  "ldap.ldbm.maxentrycachesize": "['cn=monitor,cn=userRoot,cn=ldbm database,cn=plugins,cn=config']['maxentrycachesize']",
  "ldap.modifyentryops_per_sec": "['cn=snmp,cn=monitor']['modifyentryops']",
  "ldap.referralsreturned": "['cn=snmp,cn=monitor']['referralsreturned']",
  "ldap.removeentryops": "['cn=snmp,cn=monitor']['removeentryops']",
  "ldap.searchops_per_sec": "['cn=snmp,cn=monitor']['searchops']",
  "ldap.wholesubtreesearchops_per_sec": "['cn=snmp,cn=monitor']['wholesubtreesearchops']",
  "ldap.connections": "['cn=snmp,cn=monitor']['connections']",
  "_meta": "['_meta']",
  "_meta.timestamp": "['_meta']['timeStamp']"
}

have_cache=False

parser = argparse.ArgumentParser(description='Wrapper for Zabbix 2.4')
parser.add_argument('key', metavar='Key', type=str, nargs='?', help='key to return a value for')
parser.add_argument('-a', action='store_true', help='Show all Keys and their data')
parser.add_argument('-c', action='store_true', help='Generate a list of UserParameter statements to use in a zabbix_agentd.conf file')

try:
  args=parser.parse_args()
except SystemExit as err:
  if err.code == 2: parser.print_help()
  sys.exit(err.code)

if not args.key and not args.a and not args.c:
  print("Error: Missing key to retrieve")
  parser.print_help()
  sys.exit(1)

if cfg.cache_file and cfg.cache_max_age:
  if os.path.exists(cfg.cache_file):
    age = time.time() - os.stat(cfg.cache_file)[stat.ST_MTIME]
    if age<=cfg.cache_max_age:
      have_cache=True
  
try:
  if have_cache:
    # print("Loading Cache (%d)" % (age))
    data=json.load(open(cfg.cache_file))
  else:
    data=get_and_group()
    json.dump(data,open(cfg.cache_file,'w'))
except IOError as err:
  # print err
  if have_cache:
    data=get_and_group()

if args.key:
  value=eval("data%s" % (key_map[args.key]))
  print (value)
elif args.a:
  for key in sorted(key_map.keys()):
    value=eval("data%s" % (key_map[key]))
    # print("%s : %s  (%s)" %(key,value,key_map[key]))
    print("%s : %s" %(key,value))
elif args.c:
  path=os.path.dirname(os.path.abspath(__file__))
  for key in sorted(key_map.keys()):
    print("UserParameter=%s,%s %s" % (key, path, key))