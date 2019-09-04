#!/usr/bin/env python

from os import path
import ldap
import json
import pprint
import sys
import re
import datetime
import yaml
import argparse
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

def build_nested_item(keys, data):
  if len(keys)>1:
    return {keys[0]:build_nested_item(keys[1:],data)}
  else:
    return {keys[0]:data}

def mergedicts(dict1, dict2):
  for k in set(dict1.keys()).union(dict2.keys()):
    if k in dict1 and k in dict2:
      if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
        yield (k, dict(mergedicts(dict1[k], dict2[k])))
      else:
        # If one of the values is not a dict, you can't continue merging it.
        # Value from second dict overrides one in first and we move on.
        yield (k, dict2[k])
        # Alternatively, replace this with exception raiser to alert you of value conflicts
    elif k in dict1:
      yield (k, dict1[k])
    else:
      yield (k, dict2[k])

def deeply_nest(data,reverse=False):
  return_dict={}
  for k in data:
    keys=k.split(',')
    if reverse:
      keys=keys[::-1]
    return_dict=dict(mergedicts(return_dict,build_nested_item(keys,data[k])))
  return return_dict

def get_ldap_dn(connection, baseDN,dn_params, ):
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
  except ldap.INVALID_CREDENTIALS as e:
    print("Invalid login credentials given")
    sys.exit(1)
  except ldap.LDAPError as e:
    print(e)
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
  except ldap.INVALID_CREDENTIALS as e:
    print( "Invalid login credentials given")
    sys.exit(1)
  except ldap.LDAPError as e:
    print(e)
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

def get_and_group(nested=False, reverse=False):
  result_set=get_ldap_data()
  for k in result_set:
    result_set[k]=group_dbordinals(result_set[k])
  if nested:
    return deeply_nest(result_set,reverse=reverse)
  else:
    return result_set

def get_discovery(deeply_nested=False, reverse=False):
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
    # first split the dn into its component parts
    if deeply_nested:
      dn_list=dn.split(',')
      if reverse:
        # Reverse the order if needed
        dn_list=dn_list[::-1]
      base_dn="']['".join(dn_list)
    else:
      base_dn=dn
    for k,v in data_set[dn]["db"].items():
      r=sub_name_regex.match(k)
      dbfile=r.group(1)
      group=re.sub("/%s" % (dbfile),"", k)

      #BASEJSON macro makes it easier to directly reference this backend.
 
      base_json="['%s']['db']['%s']" % (base_dn, k)
      i = {"{#DBNAME}": k, 
           "{#DBGROUP}":group,
           "{#DBFILE}": dbfile,
           "{#DBORDINAL}":v["ordinal"],
           "{#BASEJSON}":base_json}
      result_set["data"].append(i)

  return result_set



if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Wrapper for Zabbix 2.4')
  parser.add_argument('-d',action='store_true', help='Show Discovery data')
  parser.add_argument('-f',action='store_true', help='Use a flat data representation')
  parser.add_argument('-N',action='store_true', help='Use a Deeply nested prepresentation')
  parser.add_argument('-r',action='store_true', help='Reverse the order of the deeply nested representation')

  try:
    args=parser.parse_args()
  except SystemExit as err:
    if err.code == 2: parser.print_help()
    sys.exit(err.code)

  if args.r and not args.N:
    print("Reverse requires Deeply nested representation.")
    parser.print_help()
    sys.exit(1)

  if args.d:
    print(json.dumps(get_discovery(deeply_nested=args.N,reverse=args.r), indent=1))
  else:
    if args.f:
      result_list=[]
      for k in get_and_group(nested=False):
        result_list[k]['dn']=k
        result_list.append(result_list[k])
      print(json.dumps(result_list, indent=1))
    else:
      print(json.dumps(get_and_group(nested=args.N, reverse=args.r), indent=1))

