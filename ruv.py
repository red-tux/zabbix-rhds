import re
import ldap
import json

from csn import *

def normalizeDN(dn, usespace=False):
  # not great, but will do until we use a newer version of python-ldap
  # that has DN utilities
  ary = ldap.explode_dn(dn.lower())
  joinstr = r','
  if usespace:
    joinstr = r', '
  return joinstr.join(ary)

def escapeDNValue(dn):
  '''convert special characters in a DN into LDAPv3 escapes e.g.
  "dc=example,dc=com" -> \"dc\=example\,\ dc\=com\"'''
  for cc in (' ', '"', '+', ',', ';', '<', '>', '='):
    dn = dn.replace(cc, '\\' + cc)
  return dn

def escapeDNFiltValue(dn):
  '''convert special characters in a DN into LDAPv3 escapes
  for use in search filters'''
  for cc in (' ', '"', '+', ',', ';', '<', '>', '='):
    dn = dn.replace(cc, '\\%X' % ord(cc))
  return dn

class RUV(object):
  """RUV is Replica Update Vector
      ruv.gen is the generation CSN
      ruv.rid[1] through ruv.rid[N] are dicts - the number (1-N) is the replica ID
        ruv.rid[N][url] is the purl
        ruv.rid[N][min] is the min csn
        ruv.rid[N][max] is the max csn
        ruv.rid[N][lastmod] is the last modified timestamp
      example ruv attr:
      nsds50ruv: {replicageneration} 3b0ebc7f000000010000
      nsds50ruv: {replica 1 ldap://myhost:51010} 3b0ebc9f000000010000 3b0ebef7000000010000
      nsruvReplicaLastModified: {replica 1 ldap://myhost:51010} 292398402093
      if the tryrepl flag is true, if getting the ruv from the suffix fails, try getting
      the ruv from the cn=replica entry
  """
  genpat = r'\{replicageneration\}\s+(\w+)'
  genre = re.compile(genpat)
  ruvpat = r'\{replica\s+(\d+)\s+(.+?)\}\s*(\w*)\s*(\w*)'
  ruvre = re.compile(ruvpat)

  def __init__(self, ent, limit_to_rid=None):
    # rid is a dict
    # key is replica ID - val is dict of url, min csn, max csn
    self.rid = {}
    if limit_to_rid:
      limit_to_rid = int(limit_to_rid)
    for item in ent['nsds50ruv']:
      matchgen = RUV.genre.match(item)
      matchruv = RUV.ruvre.match(item)
      if matchgen:
        self.gen = CSN(matchgen.group(1))
      elif matchruv:
        rid = int(matchruv.group(1))
        if (limit_to_rid is None ) or (not limit_to_rid is None and limit_to_rid==rid):
          self.rid[rid] = {'url': matchruv.group(2),
                          'min': CSN(matchruv.group(3)),
                          'max': CSN(matchruv.group(4))}
      else:
        print "unknown RUV element", item
    for item in ent['nsruvReplicaLastModified']:
      matchruv = RUV.ruvre.match(item)
      if matchruv:
        rid = int(matchruv.group(1))
        if (limit_to_rid is None ) or (not limit_to_rid is None and limit_to_rid==rid):
          self.rid[rid]['lastmod'] = int(matchruv.group(3), 16)
      else:
        print "unknown nsruvReplicaLastModified item", item

  def __cmp__(self, oth):
    if self is oth:
      return 0
    if not self:
      return -1  # None is less than something
    if not oth:
      return 1  # something is greater than None
    diff = cmp(self.gen, oth.gen)
    if diff:
      return diff
    for rid in self.rid.keys():
      for item in ('max', 'min'):
        csn = self.rid[rid][item]
        csnoth = oth.rid[rid][item]
        diff = cmp(csn, csnoth)
        if diff:
          return diff
    return 0

  def __eq__(self, oth):
    return cmp(self, oth) == 0

  def dict(self):
    return {"gen": self.gen, "rid": self.rid}
  
  # def __repr__(self):
  #   print({"gen": self.gen.__str__(),"rid":self.rid.__str__()})
  #   return json.dumps({"gen": self.gen.__repr__(),"rid":self.rid})
  def reprJSON(self):
    return dict(gen= self.gen, rid=self.rid)

  # def __str__(self):
  #   return self.__repr__()

  def getdiffs(self, oth):
    """Compare two ruvs and return the differences
    returns a tuple - the first element is the
    result of cmp() - the second element is a string"""
    if self is oth:
      return (0, "RUVs are the same")
    if not self:
      return (-1, "first RUV is empty")
    if not oth:
      return (1, "second RUV is empty")
    diff = cmp(self.gen, oth.gen)
    if diff:
      return (diff, "generation [" + str(self.gen) + "] not equal to [" + str(oth.gen) + "]: likely not yet initialized")
    retstr = ''
    for rid in self.rid.keys():
      for item in ('max', 'min'):
        csn = self.rid[rid][item]
        csnoth = oth.rid[rid][item]
        csndiff = cmp(csn, csnoth)
        if csndiff:
          if len(retstr):
            retstr += "\n"
          retstr += "rid %d %scsn %s\n\t[%s] vs [%s]" % (rid, item, csn.diff2str(csnoth),
                                                            csn, csnoth)
          if not diff:
            diff = csndiff
    if not diff:
      retstr = "up-to-date - RUVs are equal"
    return (diff, retstr)

  def getRUV(self, suffix, tryrepl=False, verbose=False):
    uuid = "ffffffff-ffffffff-ffffffff-ffffffff"
    filt = "(&(nsUniqueID=%s)(objectclass=nsTombstone))" % uuid
    attrs = ['nsds50ruv', 'nsruvReplicaLastModified']
    ents = self.search_s(suffix, ldap.SCOPE_SUBTREE, filt, attrs)
    ent = None
    if ents and (len(ents) > 0):
      ent = ents[0]
    elif tryrepl:
      print "Could not get RUV from", suffix, "entry - trying cn=replica"
      ensuffix = escapeDNValue(normalizeDN(suffix))
      dn = ','.join("cn=replica,cn=%s" % ensuffix, DN_MAPPING_TREE)
      ents = self.search_s(dn, ldap.SCOPE_BASE, "objectclass=*", attrs)
    if ents and (len(ents) > 0):
      ent = ents[0]
    else:
      print "Could not read RUV for", suffix
      return None
    if verbose:
      print "RUV entry is", str(ent)
    return RUV(ent)