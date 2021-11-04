#!/usr/bin/env python3

from os import path
import ldap3
import json
import pprint
import ldap
import sys
import re
import datetime
import yaml
import argparse
from dateutil.tz import tzlocal

pp=pprint.PrettyPrinter(indent=2)

base_path=path.dirname(path.abspath(__file__))
settings=yaml.load(open(base_path+"/config.yaml"))

class RHDS_Server():
  def __init__(self,settings):
    self.uri = settings['uri']
    self.username = settings['username']
    self.password = settings['password']

    self.monitorDNs = settings['DNs']

    # not using "get_info=ldap3.ALL" for performance
    self.ldap_server = ldap3.Server(self.uri)
    self.ldap_conn = ldap3.Connection(self.ldap_server,user=self.username, 
                                       password=self.password, auto_bind=True)

  # Helper function to clean up data objects.
  # If a list of length 1 is passed in, the item itself is returned, otherwise list
  # if a dict is passed in each key is recursively iterated through for cleanup of descendant values
  # if a byte string is passed in, it is decoded for utf-8
  # int and string are returend as is
  # All other types raise an exception.
  def cleanup(self,item):
    if isinstance(item,list):
      if len(item)==1:
        return item[0]
      else:
        return item
    elif isinstance(item,dict) or isinstance(item,ldap3.utils.ciDict.CaseInsensitiveDict):
      new_dict = {}
      for k,v in item.items():
        new_dict[k]=self.cleanup(v)
      return new_dict
    elif isinstance(item,datetime.datetime):
      return item.isoformat()
    elif isinstance(item,bytes):
      return item.decode('utf-8')
    elif isinstance(item,str) or isinstance(item,int):
      return item
    else:
      raise("Unconfigured instance for cleanup, type: {}  val:{}".format(type(item),item))

  # need to clean up to pass search scope via parameters
  def get_ldap_data(self,dns):
    # ldap_server = ldap3.Server(settings['uri'], get_info=ldap3.ALL)
    # ldap_conn = ldap3.Connection(ldap_server,user=settings['username'], 
    #                             password=settings['password'], auto_bind=True)
    
    results={}
    for dn in dns:
      ldap_results = self.ldap_conn.search(dn,search_filter=self.monitorDNs[dn]['searchFilter'],
                                search_scope=self.monitorDNs[dn]['searchScope'],
                                attributes="*")
      for entry in self.ldap_conn.response:
        attr = entry['attributes']
        remove_keys=['aci','objectClass']
        if 'removeItems' in self.monitorDNs[dn].keys():
          remove_keys = remove_keys + self.monitorDNs[dn]['removeItems']
        for key in remove_keys:
          if key in attr.keys():
            del attr[key]
        results[entry['dn']] = self.cleanup(entry['attributes'])

    return results


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Wrapper for Zabbix 2.4')
  parser.add_argument('-d',action='store_true', help='Show Discovery data')
  # parser.add_argument('-f',action='store_true', help='Use a flat data representation')
  # parser.add_argument('-N',action='store_true', help='Use a Deeply nested prepresentation')
  # parser.add_argument('-r',action='store_true', help='Reverse the order of the deeply nested representation')

  try:
    args=parser.parse_args()
  except SystemExit as err:
    if err.code == 2: parser.print_help()
    sys.exit(err.code)

  rhds_server = RHDS_Server(settings)

  data = rhds_server.get_ldap_data(settings['DNs'].keys())
  # pp.pprint(data)
  print(json.dumps(data, indent=2, default=str))

  print()

