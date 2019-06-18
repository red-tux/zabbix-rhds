#!/usr/bin/env python

import ldap
import json
import pprint
import sys
import re
import datetime
from dateutil.tz import tzlocal

import config as cfg


pp = pprint.PrettyPrinter(indent=2)

def get_ldap_dn(connection, baseDN,dn_params):
  searchScope=dn_params["searchScope"]
  searchFilter=dn_params["searchFilter"]
  retrieveAttributes=dn_params["retrieveAttributes"]
  removeItems=dn_params.get("removeItems")
  try:
    ents = connection.search_s(baseDN, searchScope, searchFilter, retrieveAttributes)
    result_set = {}
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

def get_discovery():
  result_set={"data":[]}

  # Setup an ldap query to get cn=monitor to find out all the database back ends
  monitor_dn={"cn=monitor": {
                "searchScope" : ldap.SCOPE_SUBTREE,
                "retrieveAttributes" : None,
                "searchFilter" : "ObjectClass=*"}}
  monitor_data=get_ldap_data(dns=monitor_dn)
  backend_dns={}

  # loop through the backends found and set up anothery query for each of the db backends
  for backend in monitor_data["cn=monitor"]["backendmonitordn"]:
    backend_dns[backend]={"searchScope" : ldap.SCOPE_SUBTREE,
                          "retrieveAttributes" : None,
                          "searchFilter" : "ObjectClass=*"}

  data_set=get_ldap_data(dns=backend_dns)

  # parse out the ordinal data in the result set
  for k in data_set:
    data_set[k]=group_dbordinals(data_set[k])

  sub_name_regex=re.compile(r".*\/(.*)")
  
  # loop through the backends and build the discovery macros
  for dn in backend_dns:
    for k,v in data_set[dn]["db"].items():
      r=sub_name_regex.match(k)
      dbfile=r.group(1)
      group=re.sub("/%s" % (dbfile),"", k)

      #BASEJSON macro makes it easier to directly reference this backend.
      base_json="['%s'].db['%s']" % (dn, k)
      i = {"{#DBNAME}": k, 
           "{#DBGROUP}":group,
           "{#DBFILE}": dbfile,
           "{#DBORDINAL}":v["ordinal"],
           "{#BASEJSON}":base_json}
      result_set["data"].append(i)

  return result_set

if __name__ == "__main__":
  print json.dumps(get_discovery(), indent=1)
