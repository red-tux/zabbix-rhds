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
from  get_data import *

# With the YAML config file, I need to still "fake" the old python based config file
# just in case it's still in use.
class Struct:
  def __init__(self, **entries):
    self.__dict__.update(entries)

settings=yaml.load(open(base_path+"/config.yaml"))
cfg = Struct(**settings)

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
