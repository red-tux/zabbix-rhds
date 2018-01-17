#!/usr/bin/env python

import ldap
import json
import pprint
#import sys
import re
import datetime
from dateutil.tz import tzlocal

import config as cfg

#reload(sys)
#sys.setdefaultencoding("ISO-8859-1")

pp = pprint.PrettyPrinter(indent=2)

def get_ldap_data():
  try:
    l = ldap.initialize(cfg.uri)
    l.protocol_version=ldap.VERSION3
    l.simple_bind(cfg.username, cfg.password)
  except ldap.LDAPError, e:
    print e

  try:
    ldap_result_id = l.search(cfg.baseDN, cfg.searchScope, cfg.searchFilter, cfg.retrieveAttributes)
    result_set = {}
    while 1:
      result_type, result_data = l.result(ldap_result_id,0)
      if (result_data == []):
        break
      else:
        if result_type == ldap.RES_SEARCH_ENTRY:
          #data is returned as a tuple, let's iterate through the tuple, building the hash
          for dn,val in result_data:
            #print dn
            for k,v in val.items():
              if isinstance(v,list) and len(v)==1:
                val[k]=v[0]
            # remove some unneeded entries
            val.pop('objectClass',None)
            val.pop('cn',None)
            result_set[dn]=val
  except ldap.LDAPError, e:
    print e
  now=datetime.datetime.now(tzlocal())
  result_set["_meta"]={
    "uri":cfg.uri,
    "bindDN":cfg.username,
    "searchFilter":cfg.searchFilter,
    "baseDN":cfg.baseDN,
    "timeStamp":now.strftime("%Y-%m-%d %H:%M:%S %Z")
  }
  return result_set


def group_dbordinals(entry):
  #Some entries have ordinal values associated with them, let's group them
  # ex: dbfilename-70, dbfilepagein-70, dbfilecachehit-70
  regex = re.compile(r'(db.*)-([0-9]+)')

  found_ords=set()
  dbitems={}
  for i in entry.keys():
    r=regex.match(i)
    if r:
      g1 = r.group(1)  #entry name eg: dbfilename
      g2 = r.group(2)  #entry ordinal eg: 70
      found_ords.add(g2)
      if dbitems.get(g2,None) or None:  #check for existance
        dbitems[g2][g1] = entry[i]
      else:
        dbitems[g2]={g1:entry[i]}
      entry.pop(i)
  for i in found_ords:
    if dbitems[i].get("dbfilename",None) or None:
      k = dbitems[i]["dbfilename"]
      dbitems[k]=dbitems[i]
      dbitems[k].pop("dbfilename")
      dbitems[k]["ordinal"]=i
      dbitems.pop(i)
  if found_ords:
    entry["db"]=dbitems
  return entry

result_set=get_ldap_data()
#print "finished reading"
#print json.dumps(result_set, indent=1)
#pp.pprint(result_set)
#pp.pprint(result_set.keys())
for k in result_set:
  result_set[k]=group_dbordinals(result_set[k])

print json.dumps(result_set, indent=1)
