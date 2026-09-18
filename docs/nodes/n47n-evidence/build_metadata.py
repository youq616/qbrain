import json,hashlib,shutil
from pathlib import Path
out=Path('/mnt/data/n47n-evidence'); art=out/'artifacts';art.mkdir(exist_ok=True)
sha='a587e1751cedf83075e3ff9b78627c953e3b807a';tree='3c2b5ef5f1ce76d271f19e235f33703120d4891c';repo='youq616/qbrain'
runs={'n44':35358824749,'n42':35358824750}
checkout='Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262';post='Post '+checkout
upload='Run actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
def steps(middle,tail=(8,9)):
 return [(1,'Set up job'),(2,checkout)]+[(i+3,s) for i,s in enumerate(middle)]+[(tail[0],post),(tail[1],'Complete job')]
jobdata={
'n44':[
(105644879154,'batch-sanitized',steps(['Instrumented production batch and prior read-only recall',upload])),
(105644879196,'windows-http-2022',steps(['Build and validate the same HTTP source on Server 2022',upload])),
(105644878851,'windows',steps(['Full native application build','Native bounded WinHTTP production transport fixtures','Exact retrieval differential checks and synthetic baseline benchmark','Embedding contracts and production model isolation','CJK literal page recall and memory endpoint regression','Evidence-backed fact lifecycle and source/write boundaries','Atomic lifecycle batch and read-only preview','Reversible fact archival and advisory lifecycle inspection','Opt-in local event-to-fact promotion and installer consent','Opt-in Hook fact recall and unified context budget','Query-directed recall with complete counter-evidence','Paired conflict inspection and source boundaries','Real memory MCP hooks context and local-config process tests','PowerShell 5.1 transport and reversible installation','PowerShell 7 transport and reversible installation','Full original regression plus context unit group','Verify all gates and package exact tested binary',upload,upload],(42,43))),
(105644879011,'source',steps(['Run git archive --format=zip --output=qbrain-source.zip HEAD',upload])),
(105644879055,'portable',steps(['Build and exercise production processes without model credentials',upload])),
(105652033031,'publish-cjk-preview',None),(105652031748,'publish-fact-preview',None)],
'n42':[(105644722553,'windows',steps(['Full native MSVC application build','Real executable MCP source and read-boundary integration','Original full regression suite plus N42 tests','Upload native logs even on failure'],(12,13))),
(105644722481,'portable',steps(['Compile and run focused tests'],(6,7))),
(105644722229,'source',steps(['Archive exact source commit',upload]))]}
meta={'schema_version':1,'repository':repo,'source_commit':sha,'source_tree':tree,'runs':{},'artifacts':{},'snapshot_note':'Normalized from live GitHub connector run/jobs/artifact reads on 2026-09-18. Not a raw signed GitHub response. Job source/attempt come from containing run where the step-summary endpoint omits them; source is separately checked in archive and native logs.'}
for label,rows in jobdata.items():
 run={'id':runs[label],'path':f'.github/workflows/{label}-validation.yml','head_sha':sha,'repository':repo,'head_repository':repo,'status':'completed','conclusion':'success','event':'push','run_attempt':1,'html_url':f'https://github.com/{repo}/actions/runs/{runs[label]}','jobs_total_count':len(rows),'jobs':[]}
 for id,name,ss in rows:
  run['jobs'].append({'id':id,'name':name,'run_id':runs[label],'status':'completed','head_sha':sha,'run_attempt':1,'conclusion':'success' if ss else 'skipped','steps':[{'number':n,'name':s,'status':'completed','conclusion':'success'} for n,s in ss] if ss else None})
 meta['runs'][label]=run
pins=[
('source','n44',10553760842,'qbrain-n44-source','n47n-source-a587e175.zip',11743326,'cedf0a9936a75b33e21cc1dbd00946e3be130a30dbcf096e87fd218fab53096b'),
('windows','n44',10553934668,'qbrain-n44-windows-logs','n47n-n44-windows.zip',120374,'db75e9072ac56a53831b18eed8ebf0f60aa5bfc474bfe5d5b2b0c7656ebf51ae'),
('package','n44',10554099548,'qbrain-n44-windows-development-package','n47n-n44-package.zip',2111147,'2747a8bdb6200c924eb25dd77eae978dd6e069c469187e4f22ef46a08e794de7'),
('server2022','n44',10554207326,'qbrain-n46f-server2022-http-evidence','n47n-n44-server2022.zip',20959,'fdc022cdd4195daf780a5ef922c1cd120d95b75624140097a1c3a034b87ca554'),
('portable','n44',10553667254,'qbrain-n44-portable-logs','n47n-n44-portable.zip',73049,'c5495c328b5024b2375c32ec33964a9869b14688d43242ffcf774878fbf77fdc'),
('sanitizer','n44',10554216185,'qbrain-n47g-sanitizer-evidence','n47n-n44-sanitizer.zip',26434,'37ee6316a7690c1458a52d64a444d4c82ffc25249bb1041d38ae345d1003309e'),
('n42-windows','n42',10554018159,'qbrain-n42-windows-logs','n47n-n42-windows.zip',30638,'cb7bd5befd1aebe2915aa6ad80cde99c51ee5b9d25354573456444b9e01b8f91')]
for label,run,id,name,file,size,h in pins:
 p=Path('/mnt/data')/file;raw=p.read_bytes()
 if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=h: raise ValueError('artifact bytes: '+label)
 shutil.copyfile(p,art/(label+'.zip'))
 meta['artifacts'][label]={'id':id,'name':name,'run_id':runs[run],'head_sha':sha,'expired':False,'sha256':h,'size_in_bytes':size,'file':label+'.zip'}
p=out/'CI-METADATA.json';p.write_text(json.dumps(meta,indent=2)+'\n');print(hashlib.sha256(p.read_bytes()).hexdigest())
