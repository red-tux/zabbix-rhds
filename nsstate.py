import datetime
import time
from struct import pack, unpack, calcsize

class NSState(object):

  def __init__(self,nsstate):
    if pack('<h', 1) == pack('=h',1):
      # print "Little Endian"
      end = '<'
    elif pack('>h', 1) == pack('=h',1):
      # print "Big Endian"
      end = '>'
    else:
      print "Unknown Endian"
      sys.exit(-1) # blow up
    # print "For replica", dn
    thelen = len(nsstate)
    if thelen <= 20:
      pad = 2 # padding for short H values
      timefmt = 'I' # timevals are unsigned 32-bit int
    else:
      pad = 6 # padding for short H values
      timefmt = 'Q' # timevals are unsigned 64-bit int

    base_fmtstr = "H%dx3%sH%dx" % (pad, timefmt, pad)
    # print "  fmtstr=[%s]" % base_fmtstr
    # print "  size=%d" % calcsize(base_fmtstr)
    # print "  len of nsstate is", thelen
    fmtstr = end + base_fmtstr
    (self.rid, self.sampled_time, self.local_offset, self.remote_offset, self.seq_num) = unpack(fmtstr, nsstate)
    now = int(time.time())
    self.tdiff = now-self.sampled_time
    wrongendian = False
    try:
      self.tdelta = datetime.timedelta(seconds=self.tdiff)
      wrongendian = self.tdelta.days > 10*365
    except OverflowError: # int overflow
      wrongendian = True
    # if the sampled time is more than 20 years off, this is
    # probably the wrong endianness
    if wrongendian:
      # print "The difference in days is", tdiff/86400
      # print "This is probably the wrong bit-endianness - flipping"
      end = flipend(end)
      fmtstr = end + base_fmtstr
      (self.rid, self.sampled_time, self.local_offset, self.remote_offset, self.seq_num) = unpack(fmtstr, nsstate)
      self.tdiff = now-sampled_time
      self.tdelta = timedelta(seconds=self.tdiff) 
    self.gen_csn= "%08x%04d%04d0000" % (self.sampled_time, self.seq_num, self.rid)

  def flipend(self,end):
      if end == '<':
          return '>'
      if end == '>':
          return '<'

  def __str__(self):
    return "rid: " + str(self.rid) + " sampled_time: " + str(self.sampled_time) + \
           " seq_num: " + str(self.seq_num)
           #self.local_offset, self.remote_offset