import re
import datetime
import time
import json
import pprint

class CSN(object):
  """CSN is Change Sequence Number
      csn.ts is the timestamp (time_t - seconds)
      csn.seq is the sequence number (max 65535)
      csn.rid is the replica ID of the originating master
      csn.subseq is not currently used"""
  csnpat = r'(.{8})(.{4})(.{4})(.{4})'
  csnre = re.compile(csnpat)

  def __init__(self, csnstr):
    match = CSN.csnre.match(csnstr)
    self.ts = 0
    self.seq = 0
    self.rid = 0
    self.subseq = 0
    if match:
      self.ts = int(match.group(1), 16)
      self.seq = int(match.group(2), 16)
      self.rid = int(match.group(3), 16)
      self.subseq = int(match.group(4), 16)
    elif csnstr:
      self.ts = 0
      self.seq = 0
      self.rid = 0
      self.subseq = 0
      print csnstr, "is not a valid CSN"

  def csndiff(self, oth):
    return (oth.ts - self.ts, oth.seq - self.seq, oth.rid - self.rid, oth.subseq - self.subseq)

  def __cmp__(self, oth):
    if self is oth:
      return 0
    (tsdiff, seqdiff, riddiff, subseqdiff) = self.csndiff(oth)

    diff = tsdiff or seqdiff or riddiff or subseqdiff
    ret = 0
    if diff > 0:
      ret = 1
    elif diff < 0:
      ret = -1
    return ret

  def __eq__(self, oth):
    return cmp(self, oth) == 0

  def diff2str(self, oth):
    retstr = ''
    diff = oth.ts - self.ts
    if diff > 0:
      td = datetime.timedelta(seconds=diff)
      retstr = "behind by %s" % td
    elif diff < 0:
      td = datetime.timedelta(seconds=-diff)
      retstr = "ahead by %s" % td
    else:
      diff = oth.seq - self.seq
      if diff:
        retstr = "seq differs by %d" % diff
      elif self.rid != oth.rid:
        retstr = "rid %d not equal to rid %d" % (self.rid, oth.rid)
      else:
        retstr = "equal"
    return retstr

  def timediff(self,oth):
    diff = oth.ts - self.ts
    return diff

  def seqdiff(self,oth):
    return oth.seq-self.seq

  def reprJSON(self):
    return dict(time= time.strftime("%x %X", time.localtime(self.ts)),
                seq= self.seq,
                rid= self.rid,
                subseq= self.subseq)

  def __repr__(self):
    return time.strftime("%x %X", time.localtime(self.ts)) + " seq: " + str(self.seq) + " rid: " + str(self.rid)

  def __str__(self):
    return self.__repr__()