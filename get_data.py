#!/usr/bin/env python

from os import path
import ldap
import json
import pprint
import sys
import re
import datetime
import yaml
from dateutil.tz import tzlocal

# With the YAML config file, I need to still "fake" the old python based config file
# just in case it's still in use.
class Struct:
  def __init__(self, **entries):
    self.__dict__.update(entries)
base_path=path.dirname(path.abspath(__file__))
settings=yaml.load(open(base_path+"/config.yaml"))
cfg = Struct(**settings)

pp = pprint.PrettyPrinter(indent=2)

def get_ldap_dn(connection, baseDN,dn_params):
  searchScope=dn_params.get("searchScope",ldap.SCOPE_SUBTREE)
  searchFilter=dn_params["searchFilter"]
  retrieveAttributes=dn_params.get("retrieveAttributes")
  removeItems=dn_params.get("removeItems")
  try:
    # If we have a single object, build an iterator, otherwise use the iterator
    iter = (searchFilter,) if not isinstance(searchFilter, (tuple, list)) else searchFilter
    result_set = {}
    for filter in iter:
      ents = connection.search_s(baseDN, searchScope, filter, retrieveAttributes)
      for ent in ents:
        # data is returned as a tuple, 0 is the dn, 1 is the object
        dn=ent[0]
        val=ent[1]
        #print dn
        for k,v in val.items():
          if removeItems and k in removeItems:
            val.pop(k)
          elif isinstance(v,list) and len(v)==1:
            val[k]=v[0]
        # remove some unneeded entries
        val.pop('objectClass',None)
        val.pop('cn',None)
        result_set[dn]=val
  except ldap.INVALID_CREDENTIALS, e:
    print "Invalid login credentials given"
    sys.exit(1)
  except ldap.LDAPError, e:
    print e
    raise

  return result_set

def get_ldap_data(dns = cfg.DNs):
  try:
    if cfg.NO_TLS_REQCERT:
      ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    l = ldap.initialize(cfg.uri)
    l.protocol_version=ldap.VERSION3
    result=l.simple_bind(cfg.username, cfg.password)
    l.result(result)  #Flush out errors if there are any

    result_set = {}

    for dn in dns:
      result_set.update(get_ldap_dn(l,dn,dns[dn]))
  except ldap.INVALID_CREDENTIALS, e:
    print "Invalid login credentials given"
    sys.exit(1)
  except ldap.LDAPError, e:
    print e
    raise

  now=datetime.datetime.now(tzlocal())
  result_set["_meta"]={
    "uri":cfg.uri,
    "DNs":cfg.DNs,
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

def get_and_group():
  result_set=get_ldap_data()
  for k in result_set:
    result_set[k]=group_dbordinals(result_set[k])
  return result_set

if __name__ == "__main__":
  print json.dumps(get_and_group(), indent=1)
