#!/usr/bin/env python

import ldap
import json
import pprint
import sys
import config as cfg

reload(sys)
sys.setdefaultencoding("ISO-8859-1")

pp = pprint.PrettyPrinter(indent=2)


try:
  l = ldap.initialize(cfg.uri)
  l.protocol_version=ldap.VERSION3
  l.simple_bind(cfg.username, cfg.password)
except ldap.LDAPError, e:
  print e

baseDN = "cn=config"
searchScope = ldap.SCOPE_SUBTREE
retrieveAttributes = None
searchFilter = "(|(cn=features)(cn=monitor)(cn=snmp)(cn=replication))"
#searchFilter = "cn=snmp"

try:
  ldap_result_id = l.search(baseDN, searchScope, searchFilter) #, retrieveAttributes)
  result_set = {}
  while 1:
    result_type, result_data = l.result(ldap_result_id,0)
    if (result_data == []):
      break
    else:
      if result_type == ldap.RES_SEARCH_ENTRY:
        #data is returned as a tuple, let's iterate through the tuple, building the hash
        for dn,val in result_data:
          print dn
          for k,v in val.items():
            if isinstance(v,list) and len(v)==1:
              val[k]=v[0]
          # remove some unneeded entries
          val.pop('objectClass',None)
          val.pop('cn',None)
          result_set[dn]=val
except ldap.LDAPError, e:
  print e

print "finished reading"
print json.dumps(result_set, indent=1)
#pp.pprint(result_set)
