#!/usr/bin/env python

from lxml import etree

tree=etree.parse("TemplateRHDSLDAP.xml")
# print(etree.tostring(tree, pretty_print=True))
tree_root=tree.getroot()
print(len(tree.getroot()))
preprocessing_steps=tree_root.xpath('/zabbix_export/templates/template/items/item/preprocessing/step')
for i in preprocessing_steps:
  if i[0].text=='12' and i[1].text[0]=='$':
    print(i[1].text)
    i[1].text=i[1].text.replace(",","']['")
    print(i[1].text)
  # preprocessing = i.xpath('preprocessing/step')
  # print(len(preprocessing),preprocessing)
  # print(preprocessing)
  # print([child[1].text for child in preprocessing])
  # if len(preprocessing)>1:
  #   print(preprocessing[1][1])
# print(template_data.getnext().tag)
# for name in tree.iter('item'):
#   print(name.attrib)

with open('TemplateRHDSLDAP-parsed.xml','wb') as f:
  f.write(etree.tostring(tree_root, pretty_print=True))