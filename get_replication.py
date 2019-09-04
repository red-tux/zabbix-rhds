#!/usr/bin/env python

from os import path
import ldap
import json
import pprint
import yaml
import time
import datetime
import re
import argparse
from urlparse import urlparse
from get_data import *
from ruv import *
from nsstate import *

class ComplexEncoder(json.JSONEncoder):
  def default(self, obj):
    if hasattr(obj,'reprJSON'):
      return obj.reprJSON()
    else:
      return json.JSONEncoder.default(self, obj)

class Settings:
  def __init__(self, conf_file):
    if path.exists(conf_file):
      self._values={}
      self._values.update(yaml.load(open(conf_file)))
    else:
      raise Exception("Config File not Found")
  
  def __getattr__(self,key):
    if key in self._values:
      return self._values[key]
    else:
      return None

cfg=Settings(base_path+"/config.yaml")

def connect(uri, bind_dn, bind_password):
  if cfg.NO_TLS_REQCERT:
    ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
  l = ldap.initialize(uri)
  if cfg.timeout:
    l.set_option(ldap.OPT_NETWORK_TIMEOUT,cfg.timeout)
  l.protocol_version=ldap.VERSION3
  result=l.simple_bind(bind_dn, bind_password)
  l.result(result)  #Flush out errors if there are any
  return l

# TODO  Add nesting/reversing logic to dnd of 'for replica_dn' loop below
def get_replication_data():
  master=connect(cfg.uri, cfg.username, cfg.password)
  result_set = {}

  # Query the LDAP server to find out what replication agreements it has
  replicant_search={"searchScope":ldap.SCOPE_SUBTREE, 
                  "searchFilter":"objectClass=nsDS5ReplicationAgreement",
                  "removeItems": ["nsDS5ReplicaCredentials","nsDS5ReplicaBindDN"]}
  replicant_details = get_ldap_dn(master,'cn=mapping tree,cn=config',replicant_search)

  # dictionary containing the infomration about the replicas we will connect to
  # along with the connection object
  replicants={}

  for r in replicant_details:
    # print(replicant_details[r])
    r_values=replicant_details[r]
    r_data={}  # This will be appended to the replicant details at the end of the loop
    if r_values["nsDS5ReplicaTransportInfo"]=="LDAP":
      transport="ldap"
    elif r_values["nsDS5ReplicaTransportInfo"]=="SSL":
      transport="ldaps"
    else:
      raise Exception("Unknown TransportInfo '%s' for %s" %(r_values["nsDS5ReplicaTransportInfo"],r))
    uri = "%s://%s:%s" % (transport, r_values["nsDS5ReplicaHost"],
                          r_values["nsDS5ReplicaPort"])
    try:                        
      r_data['connection']=connect(uri,cfg.username,cfg.password)
    except ldap.SERVER_DOWN:
      r_data['connection']=None
      r_data['connection_msg']="Unable to connect within timeout"
    except ldap.INVALID_CREDENTIALS as e:
      r_data['connection']=None
      r_data['connection_msg']="Invalid login credentials"


    # extract a short description of the replication using the DN.
    # First split the string on cn=, trim the whitespace and remove the last character which will be a comma
    r_data['short_desc']=re.split("cn=",r)[1].strip()[:-1]
    r_data['status']={}
    m = re.search(r'\((.+)\) (.*)',r_values['nsds5replicaLastUpdateStatus'])
    if m:
      r_data['status']['errno']=m.group(1)
      r_data['status']['errstr']=m.group(2)
    r_details=replicant_details[r]
    r_details.update(r_data)
    replicant_details[r]= r_details

  ruv_search={"searchScope":ldap.SCOPE_SUBTREE, 
              "searchFilter":"(&(objectclass=nstombstone)(nsUniqueId=ffffffff-ffffffff-ffffffff-ffffffff))",
              "removeItems": ["nsDS5ReplicaCredentials","nsDS5ReplicaBindDN"]}

  # loop through each of the root DNs which are replicated              
  for replica_dn_item in cfg.replicaDNs:
    dn_result_set={}
    if isinstance(replica_dn_item,dict):
      replica_dn=replica_dn_item.keys()[0]
      replica_dn_label=replica_dn_item[replica_dn]['label']
    else:
      replica_dn=replica_dn_item
      replica_dn_label=replica_dn

    # Get the RUV information for the source server
    dn_entry="cn=replica,cn=%s,cn=mapping tree,cn=config" %(escapeDNFiltValue(replica_dn))
    master_ruv_data=get_ldap_dn(master,replica_dn,ruv_search)
    dn_result_set['master_ruv']=master_ruv_data[dn_entry]

    dn_result_set['master_ruv']['nsState']=NSState(master_ruv_data[dn_entry]['nsState'])

    # Leaving this for now.  If limit_to_rid is passed in, only the RIDs which match
    # the one passed in are stored in the final object.  Will likely require some
    # rework to allow for finer grained testing
    # master_ruv = RUV(master_ruv_data[dn_entry],limit_to_rid=master_ruv_data[dn_entry]['nsDS5ReplicaId'])
    master_ruv = RUV(master_ruv_data[dn_entry])

    dn_result_set['master_ruv']['ruv']=master_ruv
    replicant_ruv = {}
    replicant_ruv_data={}

    # Loop through the replicant servers and compare RUV information.
    for r in replicant_details:
      r_result_set={}
      r_details=replicant_details[r]
      replicant_connection=r_details['connection']
      replicant_desc=r_details['short_desc']
      replicant_hostname=r_details["nsDS5ReplicaHost"]
      if replicant_connection:
        r_result_set=get_ldap_dn(replicant_connection,replica_dn,ruv_search)[dn_entry]

        # Leaving this for now.  If limit_to_rid is passed in, only the RIDs which match
        # the one passed in are stored in the final object.  Will likely require some
        # rework to allow for finer grained testing
        # r_result_set['ruv']=RUV(r_result_set,limit_to_rid=master_ruv_data[dn_entry]['nsDS5ReplicaId'])
        r_result_set['ruv']=RUV(r_result_set)

        r_result_set['nsState']=NSState(r_result_set['nsState'])
        rc,status = master_ruv.getdiffs(r_result_set['ruv'])
        r_result_set["ruv_equality"]=rc
        r_result_set["ruv_status"]=status
        r_result_set["connect_status"]="Connection Good"
        r_result_set["status"]=r_details["status"]
        r_result_set["have_data"]=True
      else:
        r_result_set["connect_status"]=replicant_details[r]['connection_msg']
        r_result_set["have_data"]=False

      r_result_set["connected_to"]=replicant_hostname
      r_result_set["description"]=replicant_desc
    

      dn_result_set[replicant_desc]=r_result_set

    result_set[replica_dn_label]=dn_result_set

  return result_set

def get_replication_discovery():
  repl_data = get_replication_data()
  discovery_data={"data":[]}
  for root in repl_data:
    for agreement in repl_data[root]:
      if agreement not in ('master_ruv'):
        disc_item={}
        disc_item['{#ROOT}']=root
        disc_item['{#AGREEMENT}']=agreement
        disc_item['{#BASEJSON}']="['%s']['%s']" % (root, agreement)
        discovery_data["data"].append(disc_item)
  
  return discovery_data

if __name__ == "__main__":   
  parser = argparse.ArgumentParser(description='Wrapper for Zabbix 2.4')
  parser.add_argument('-d',action='store_true', help='Show Discovery data')
  # parser.add_argument('-N',action='store_true', help='Use a Deeply nested prepresentation')
  # parser.add_argument('-r',action='store_true', help='Reverse the order of the deeply nested representation')

  try:
    args=parser.parse_args()
  except SystemExit as err:
    if err.code == 2: parser.print_help()
    sys.exit(err.code)

  # if args.r and not args.N:
  #   print("Reverse requires Deeply nested representation.")
  #   parser.print_help()
  #   sys.exit(1)

  if args.d:
    print(json.dumps(get_replication_discovery(), indent=1))
  else:
    print(json.dumps(get_replication_data(), indent=2, cls=ComplexEncoder))