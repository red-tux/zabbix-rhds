#!/usr/bin/env python

from os import path
import ldap
import json
import pprint
import yaml
import time
import datetime
import re
from urlparse import urlparse
from get_data import *
from ruv import *
from nsstate import *


class Settings:
  def __init__(self, conf_file):
    if path.exists(conf_file):
      self.__dict__.update(yaml.load(open(conf_file)))
    else:
      raise Exception("Config File not Found")

try:
  cfg=Settings("config.yaml")
except:
  print("unable to find Config file, falling back to old config file")
  import config as cfg

# pp = pprint.PrettyPrinter(indent=2)


# pp.pprint(cfg)

# pp.pprint(cfg.DNs)

def connect(uri, bind_dn, bind_password):
  try:
    if cfg.NO_TLS_REQCERT:
      ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    l = ldap.initialize(uri)
    if cfg.timeout:
      l.set_option(ldap.OPT_NETWORK_TIMEOUT,cfg.timeout)
    l.protocol_version=ldap.VERSION3
    result=l.simple_bind(bind_dn, bind_password)
    l.result(result)  #Flush out errors if there are any
  except ldap.INVALID_CREDENTIALS, e:
    print("Invalid login credentials for %s" % (uri))
    sys.exit(1)
  except ldap.LDAPError, e:
    print e
    raise
  return l

def parse_nsstate(nsstate):
  state=NSState(nsstate)
  ts=int(state.sampled_time)
  return_val={}
  return_val['raw']=nsstate
  return_val['sample_time']=str(datetime.datetime.fromtimestamp(ts))
  return_val['tdiff']=state.tdiff
  return_val['rid']=state.rid
  return_val['seq_num']=state.seq_num
  return_val['gen_csn']=state.gen_csn
  return_val['local_offset']=state.local_offset
  return_val['remote_offset']=state.remote_offset

  return return_val


print("Connecting to: %s" % (cfg.uri))

master=connect(cfg.uri, cfg.username, cfg.password)
result_set = {}

replicant_search={"searchScope":ldap.SCOPE_SUBTREE, 
                "searchFilter":"objectClass=nsDS5ReplicationAgreement",
                "removeItems": ["nsDS5ReplicaCredentials","nsDS5ReplicaBindDN"]}
replicant_details = get_ldap_dn(master,'cn=mapping tree,cn=config',replicant_search)

# pp.pprint(replicant_details)

# dictionary containing the host name and connection object
replicants={}

for r in replicant_details:
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

  # extract a short description of the replication using the DN.
  # First split the string on cn=, trim the whitespace and remove the last character which will be a comma
  r_data['short_desc']=re.split("cn=",r)[1].strip()[:-1]
  r_data['status']={}
  m = re.search('\((.+)\) (.*)',r_values['nsds5replicaLastUpdateStatus'])
  if m:
    r_data['status']['errno']=m.group(1)
    r_data['status']['errstr']=m.group(2)
  r_details=replicant_details[r]
  r_details.update(r_data)
  replicant_details[r]= r_details

ruv_search={"searchScope":ldap.SCOPE_SUBTREE, 
            "searchFilter":"(&(objectclass=nstombstone)(nsUniqueId=ffffffff-ffffffff-ffffffff-ffffffff))",
            "removeItems": ["nsDS5ReplicaCredentials","nsDS5ReplicaBindDN"]}
             
for replica_dn in cfg.replicaDNs:
  dn_result_set={}
  dn_entry="cn=replica,cn=%s,cn=mapping tree,cn=config" %(escapeDNFiltValue(replica_dn))
  master_ruv_data=get_ldap_dn(master,replica_dn,ruv_search)
  dn_result_set['master_ruv']=master_ruv_data[dn_entry]

  dn_result_set['master_ruv']['nsState']=parse_nsstate(master_ruv_data[dn_entry]['nsState'])

  master_ruv = RUV(master_ruv_data[dn_entry])

  replicant_ruv = {}
  replicant_ruv_data={}

  for r in replicant_details:
    r_result_set={}
    r_details=replicant_details[r]
    replicant_connection=r_details['connection']
    # print(replicant_connection)
    replicant_desc=r_details['short_desc']
    replicant_hostname=r_details["nsDS5ReplicaHost"]
    # print(replicant_hostname)
    # time.sleep(1)
    # r_result_set=get_ldap_dn(replicant_connection,replica_dn,ruv_search)[dn_entry]
    if replicant_connection:
      # pp.pprint(get_ldap_dn(replicant_connection,replica_dn,ruv_search))
      r_result_set=get_ldap_dn(replicant_connection,replica_dn,ruv_search)[dn_entry]
      r_result_set['ruv']=RUV(r_result_set)
      r_result_set['nsState']=parse_nsstate(r_result_set['nsState'])
      # replicant_ruv[replicant_hostname]=RUV(replicant_ruv_data[replicant_hostname])
      # pp.pprint(replicant_ruv[replicant_hostname])
      # print(r_result_set['ruv'])

      # pp.pprint(master_ruv_data[dn_entry]["nsds50ruv"])
      for rid in master_ruv.rid:
        print(rid)
        # print("local ruv[%d]      %s" % (rid,master_ruv.rid[rid]))
        # print("replicant ruv[%d]  %s" % (rid,r_result_set['ruv'].rid[rid]))
        # print
      # print("master maxcsn TS: %s" % (master_ruv.))
      rc,status = master_ruv.getdiffs(r_result_set['ruv'])
      # print(status)
      r_result_set["rc"]=rc
      r_result_set["status"]=status
      # print(rc)
      r_result_set["have_data"]=True
    else:
      r_result_set["status"]="Failed to Connect"
      r_result_set["have_data"]=False
  

    dn_result_set[replicant_desc]=r_result_set

  result_set[replica_dn]=dn_result_set

pp.pprint(result_set)
