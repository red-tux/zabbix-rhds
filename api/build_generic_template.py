#!/bin/env python3
from pyzabbix.api import ZabbixAPI
import pprint
import yaml
from os import path
import argparse

pp = pprint.PrettyPrinter(indent=2)

class Template:
  def load(self,yaml_file):
    base_path=path.dirname(path.abspath(__file__))
    indata=yaml.load(open(base_path+yaml_file), yaml.Loader)

    self.name = indata['template_name']
    

def create_json_dependent(host,parent,name,key,preprocessing=[],applications=[],history='1d',value_type=3):
  item_val = zapi.item.get(hostids=host,sortfield="key_",output="extend",search={"key_":key})
  if len(item_val)>0 and item_val[0]['key_'] == key:
    print("Key '{}' found, updating".format(key))
    itemid=item_val[0]['itemid']
    print("itemid: {}   parent: {}".format(itemid,parent))
    return(zapi.item.update(itemid=itemid,name=name,key_=key,hostid=host,master_itemid=parent,
                            type=18, value_type=value_type, preprocessing=preprocessing, applications=applications,
                            history=history))
  return(zapi.item.create(name=name,key_=key,hostid=host,master_itemid=parent,
                   type=18, value_type=value_type, preprocessing=preprocessing, applications=applications,
                   history=history)['itemids'][0])

def create_key(host,name,key):
  item_val = zapi.item.get(hostids=host,sortfield="key_",output="extend",search={"key_":key})
  if len(item_val)>0 and item_val[0]['key_'] == key:
    print("Key '{}' found, skipping".format(key))
    return(item_val)
  return(zapi.item.create(name=name,key_=key,hostid=host,
                         type=0,value_type=4,applications=[2110],
                         delay="5m",history="1d"))
 
 
parser = argparse.ArgumentParser(description='Zabbix API Templatecreator script')
parser.add_argument('template', type=str,
                    help="Template to process")
parser.add_argument('-s',dest='server',type=str, required=True,
                    help='Server to connect to')
parser.add_argument('-u',dest='user',type=str, required=True,
                    help='User to use')
parser.add_argument('-p',dest='passwd',type=str, required=True,
                    help='User password')

args = parser.parse_args()

base_path=path.dirname(path.abspath(__file__))
api_info=yaml.load(open(base_path+args.template), yaml.Loader)

# Create ZabbixAPI class instance
zapi = ZabbixAPI(url=args.server, user=args.user, password=args.passwd)


master_item="dirsrv.zabbix_monitor"
tmpl_name="Template IDM Ldap Stats"

api_retval = zapi.template.get(filter={'host':[tmpl_name]},sortfield="host")
if len(api_retval) > 0 and api_retval[0]['host']==tmpl_name:
  template_id=api_retval[0]['templateid']
  print("Found, templateid: {}".format(template_id))
else:
  print("Cannot find tempalte '{}'".format(tmpl_name))
  exit(1)

print("Create master item '{}'".format(master_item))
master_item_id = create_key(template_id,master_item,master_item)[0]['itemid']

# loop through definitions in supplied yaml file
for parentkey,parentitems in api_info.items():
  preprocessing=[{'type': 12, 'params':"$['{}']".format(parentitems['dn']),
                  'error_handler':0, 'error_handler_params':''}]
  parent_id = create_json_dependent(template_id,master_item_id,parentkey,parentkey,
                         preprocessing=preprocessing,applications=[2110],value_type=4)
                         
  # parent_id will be different depending on weather the item was previously created or not
  if isinstance(parent_id,dict) and 'itemids' in parent_id:
    parent_id = parent_id['itemids'][0]

  print(parent_id)
  for key,params in parentitems['items'].items():
    key_val = "{}.{}".format(parentkey,key)
    preprocessing=[{'type': 12, 'params':"$['{}']".format(key),
                  'error_handler':0, 'error_handler_params':''}]
    print(create_json_dependent(template_id,parent_id,key_val,key_val,
                                preprocessing=preprocessing,applications=[2110],**params))
  

zapi.user.logout()