import json,hashlib,shutil
from pathlib import Path
out=Path('/mnt/data/n47m-review'); art=out/'artifacts';art.mkdir(exist_ok=True)
sha='15f6f3962984cb9a9d20c3b6a2790a9b768f119e';tree='571c24873615aa867fe037b0fb2f83975307371c';repo='youq616/qbrain'
runs={'n44':35292424683,'n42':35292424658}
checkout='Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262';post='Post '+checkout
upload='Run actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
def steps(middle,tail=(8,9)):
 return [(1,'Set up job'),(2,checkout)]+[(i+3,s) for i,s in enumerate(middle)]+[(tail[0],post),(tail[1],'Complete job')]
jobdata={
'n44':[
(105437926432,'batch-sanitized',steps(['Instrumented production batch and prior read-only recall',upload])),
(105437926577,'windows-http-2022',steps(['Build and validate the same HTTP source on Server 2022',upload])),
(105437926627,'windows',steps(['Full native application build','Native bounded WinHTTP production transport fixtures','Exact retrieval differential checks and synthetic baseline benchmark','Embedding contracts and production model isolation','CJK literal page recall and memory endpoint regression','Evidence-backed fact lifecycle and source/write boundaries','Atomic lifecycle batch and read-only preview','Reversible fact archival and advisory lifecycle inspection','Opt-in local event-to-fact promotion and installer consent','Opt-in Hook fact recall and unified context budget','Query-directed recall with complete counter-evidence','Paired conflict inspection and source boundaries','Real memory MCP hooks context and local-config process tests','PowerShell 5.1 transport and reversible installation','PowerShell 7 transport and reversible installation','Full original regression plus context unit group','Verify all gates and package exact tested binary',upload,upload],(42,43))),
(105437926736,'source',steps(['Run git archive --format=zip --output=qbrain-source.zip HEAD',upload])),
(105437926742,'portable',steps(['Build and exercise production processes without model credentials',upload])),
(105443161875,'publish-cjk-preview',None),(105443161878,'publish-fact-preview',None)],
'n42':[(105437926557,'windows',steps(['Full native MSVC application build','Real executable MCP source and read-boundary integration','Original full regression suite plus N42 tests','Upload native logs even on failure'],(12,13))),
(105437926726,'portable',steps(['Compile and run focused tests'],(6,7))),
(105437926749,'source',steps(['Archive exact source commit',upload]))]}
meta={'schema_version':1,'repository':repo,'source_commit':sha,'source_tree':tree,'runs':{},'artifacts':{},'snapshot_note':'Normalized from live GitHub connector run/jobs/artifact reads on 2026-09-18. Not a raw signed GitHub response. Job source/attempt come from containing run where the step-summary endpoint omits them; source is separately checked in archive and native logs.'}
for label,rows in jobdata.items():
 run={'id':runs[label],'path':f'.github/workflows/{label}-validation.yml','head_sha':sha,'repository':repo,'head_repository':repo,'status':'completed','conclusion':'success','event':'push','run_attempt':1,'html_url':f'https://github.com/{repo}/actions/runs/{runs[label]}','jobs_total_count':len(rows),'jobs':[]}
 for id,name,ss in rows:
  run['jobs'].append({'id':id,'name':name,'run_id':runs[label],'status':'completed','head_sha':sha,'run_attempt':1,'conclusion':'success' if ss else 'skipped','steps':[{'number':n,'name':s,'status':'completed','conclusion':'success'} for n,s in ss] if ss else None})
 meta['runs'][label]=run
pins=[
('source','n44',10526112886,'qbrain-n44-source','n47m-source-15f6f396.zip',11701859,'41f911cef1046c49144407c4c1455056523e4f6f25e3b4acb0b2868469055ed0'),
('windows','n44',10527004782,'qbrain-n44-windows-logs','n47m-n44-windows.zip',120451,'a668ebfd7ce1ca266bd03ffdca1c950fb2a1e6516c3e66f0fc7d5139244a03ae'),
('package','n44',10527004786,'qbrain-n44-windows-development-package','n47m-n44-package.zip',2109021,'680e3c67bac53dda29de49b802da693d26a024881528e2684ab41a639d32cd5c'),
('server2022','n44',10526568902,'qbrain-n46f-server2022-http-evidence','n47m-n44-server2022.zip',20925,'2fc2923b099c1d1e2a0cc391e78d681a4093acee769066e47906c2f984bffb96'),
('portable','n44',10526312901,'qbrain-n44-portable-logs','n47m-n44-portable.zip',73033,'96f4376fd5142759b6ed5de5c6161812eaccc5ca6eab89ba26e3eb21b51d3b93'),
('sanitizer','n44',10526663199,'qbrain-n47g-sanitizer-evidence','n47m-n44-sanitizer.zip',26429,'f6cdd23b287f8e4dace41ae4266181442ba9a8bf269d54bf92678eac4cab2ca3'),
('n42-windows','n42',10526128757,'qbrain-n42-windows-logs','n47m-n42-windows.zip',30623,'f07387e7e135dbe46f51cae02efff97ca82b17e9b9f653ed73bbfb1f68195f17')]
for label,run,id,name,file,size,h in pins:
 p=Path('/mnt/data')/file;raw=p.read_bytes()
 assert len(raw)==size and hashlib.sha256(raw).hexdigest()==h
 shutil.copyfile(p,art/(label+'.zip'))
 meta['artifacts'][label]={'id':id,'name':name,'run_id':runs[run],'head_sha':sha,'expired':False,'sha256':h,'size_in_bytes':size,'file':label+'.zip'}
p=out/'CI-METADATA.json';p.write_text(json.dumps(meta,indent=2)+'\n');print(hashlib.sha256(p.read_bytes()).hexdigest())
