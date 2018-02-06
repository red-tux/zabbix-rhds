#!/usr/bin/env python

import time
from threading import Timer, Thread, Event
import sys,select
import os

import get_data

initial_values={}
prev_min_values={}
current_values={}
last_update=time.time()

def print_row(format_str,row,indent=0):
  if indent>0:
    row=list(row)
    row[0]=" "*indent+row[0]
    row=tuple(row)
  print format_str.format(*row)

def show_dn(initial,prev_min,current,show_header=True,sub_key=None,indent=0,width=0):
  max_width=width

  if width==0:
    max_width=9
    for key in sorted(initial.keys()):
      if not isinstance(initial[key],str):
        continue
      if len(initial[key])>max_width:
        max_width=len(initial[key])

  row_format="{:<30} | {:>%d} | {:>%d} | {:>%d} | {:>%d} | {:>%d}" % (max_width, max_width, max_width, max_width+1, max_width+1 )

  if show_header:
    headers1=("","","","","Overall","1 Minute")
    headers2=("Field","initial","prev","current","difference", "difference")

    print row_format.format(*headers1)
    print row_format.format(*headers2)

  if sub_key:
    print " "*(indent-2) + sub_key

  for key in sorted(initial.keys()):
    if not isinstance(initial[key],str):
      show_dn(initial[key],prev_min[key],current[key],show_header=False,sub_key=key,indent=indent+2,width=max_width)
      continue

    if initial[key].isdigit():
      full_difference=int(current[key])-int(initial[key])
      if full_difference==0:
        full_difference=""

      min_difference=int(current[key])-int(prev_min[key])
      if min_difference==0:
        min_difference=""
    else:
      full_difference=""
      min_difference=""

    row=(key,initial[key],prev_min[key],current[key],full_difference,min_difference)
    print_row(row_format,row,indent=indent)

def show_snmp(initial_val,prev_min_val,current_val):
  dn="cn=snmp,cn=monitor"
  initial=initial_val[dn]
  prev_min=prev_min_val[dn]
  current=current_val[dn]

  show_dn(initial,prev_min,current)

def show_monitor(initial_val,prev_min_val,current_val):
  dn="cn=monitor"
  initial=initial_val[dn].copy()
  prev_min=prev_min_val[dn].copy()
  current=current_val[dn].copy()

  pop_keys=["version","currenttime","starttime","backendmonitordn","connection"]
  for key in pop_keys:
    initial.pop(key,None)
    prev_min.pop(key,None)
    current.pop(key,None)

  show_dn(initial,prev_min,current)

def show_db_monitor(initial_val,prev_min_val,current_val):
  initial={}
  prev_min={}
  current={}
  for db_dn in initial_val["cn=monitor"]["backendmonitordn"]:
    initial[db_dn]=initial_val[db_dn].copy()
    prev_min[db_dn]=prev_min_val[db_dn].copy()
    current[db_dn]=current_val[db_dn].copy()


  for dn in sorted(initial.keys()):
    print dn
    show_dn(initial[dn],prev_min[dn],current[dn])

class updateTimer():
  def __init__(self,t):
    self.t=t
    self.thread = Timer(self.t, self.handle_function)

  def handle_function(self):
    self.update_function()
    self.thread = Timer(self.t,self.handle_function)
    self.thread.start()

  def update_function(self):
    global prev_min_values
    global current_values
    global last_update

    last_update=time.time()

    prev_min_values=current_values.copy()
    current_values=get_data.get_and_group()

  def start(self):
    self.thread.start()

  def cancel(self):
    self.thread.cancel()

initial_values=get_data.get_and_group()
prev_min_values=initial_values
#time.sleep(5)
current_values=get_data.get_and_group()

update_thread=updateTimer(60)
update_thread.start()

#build DN list:
dn_list = ["cn=monitor","cn=snmp,cn=monitor"]

for db_dn in sorted(initial_values["cn=monitor"]["backendmonitordn"]):
  dn_list.append(db_dn)

quit=False
position=0
prev_time=0
update_needed=False

while not quit:
  cur_dn=dn_list[position]
  if (prev_time!=last_update) or update_needed:
    os.system('clear')
    print dn_list
    print cur_dn
    print position
    if cur_dn=="cn=monitor":
      show_monitor(initial_values,prev_min_values,current_values)
    elif cur_dn=="cn=snmp,cn=monitor":
      show_snmp(initial_values,prev_min_values,current_values)
    else:
      show_dn(initial_values[cur_dn],prev_min_values[cur_dn],current_values[cur_dn])
    prev_time=last_update
    update_needed=False

  i,o,e = select.select( [sys.stdin], [], [], 5)
  if (i):
    char = sys.stdin.readline().strip()
    if char=="q":
      quit=True
    elif char=="n":
      print position
      position=(position+1)%(len(dn_list))
      print position
      update_needed=True
    elif char=="p":
      print position
      position=position-1
      if position<0:
        position=len(dn_list)-1
      print position
      update_needed=True

print "Exited main loop"
update_thread.cancel()
#show_monitor(initial_values,prev_min_values,current_values)
#show_db_monitor(initial_values,prev_min_values,current_values)

