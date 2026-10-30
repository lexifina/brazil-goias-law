import json,re,collections,sys
for f in sys.argv[1:]:
  for a in json.load(open(f,encoding='utf-8'))['acts']:
    v=a['versions'][0]; ks=list(v['units'])
    nums=[int(k[4:8]) for k in ks if k.startswith('art-')]
    gaps=[(x,y) for x,y in zip(nums,nums[1:]) if y-x>1]
    dup=[k for k in ks if 'dup' in k]
    rep=[]
    for k,u in v['units'].items():
        if k=='000-titulo': continue
        marks=re.findall(r'(?m)^(§ ?\d+\S*|Parágrafo único)',u['text'])
        d=[m for m,n in collections.Counter(marks).items() if n>1]
        if d: rep.append((k,d[:3]))
        if re.search(r'(?m)^Art\.? ?\d',u['text'].split('\n',1)[1] if '\n' in u['text'] else ''): rep.append((k,'inner Art'))
    print(a['slug'], v['from'], len(ks), 'gaps',gaps[:12], 'dup',dup[:5], 'rep',rep[:12])
