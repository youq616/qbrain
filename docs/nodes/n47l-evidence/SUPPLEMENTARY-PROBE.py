# POST-RUN TRANSCRIPTION — NOT AN ORIGINAL EXECUTION ARTIFACT.
# This file was written after the actual inline tool execution, from the
# still-visible conversation context. It has NOT been executed as a file.
# The Python below transcribes the actual python3 -B heredoc used for the
# 881-case supplementary sweep plus the three original malformed-history shapes.
# Original cwd: /workspace/scratch/8ee4dd18bee0/qbrain
# Historical report input: build/takeover/multiterm-after-report-repair.json
# Do not relabel this transcription as a captured original probe/log or a rerun.
# See gate-review.md for source identities, actual output, and limitations.

import copy, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,'.ci')
from test_multiterm_report import MultitermReportTests
from validate_multiterm_report import validate_commands
import test_multiterm_process as p
T=MultitermReportTests()
results=[]
for label, mutate in [
 ('original all duplicate init success',lambda r:r.update(commands=[{'args':['init'],'exit_code':0,'expected_exit':0} for _ in range(len(p.COMMAND_SCHEDULE))])),
 ('original no command identity',lambda r:r.update(commands=[{'exit_code':0,'expected_exit':0} for _ in range(len(p.COMMAND_SCHEDULE))])),
 ('original all self asserted rejection',lambda r:r.update(commands=[{'args':['init'],'exit_code':1,'expected_exit':1} for _ in range(len(p.COMMAND_SCHEDULE))]))]:
 r=T.process_fixture();mutate(r)
 try:T.vp(r);results.append((label,'UNEXPECTED ACCEPT'))
 except ValueError:results.append((label,'REJECTED'))
for field in ('name','args','stdin_json','expected_exit','exit_code'):
 for i in range(len(p.COMMAND_SCHEDULE)):
  r=T.process_fixture();r['commands'][i].pop(field)
  try:T.vp(r);raise AssertionError((field,i,'accepted'))
  except ValueError:pass
results.append(('each required field missing per command',len(p.COMMAND_SCHEDULE)*5))
for i in range(len(p.COMMAND_SCHEDULE)-1):
 r=T.process_fixture();r['commands'][i],r['commands'][i+1]=r['commands'][i+1],r['commands'][i]
 try:T.vp(r);raise AssertionError((i,'swap accepted'))
 except ValueError:pass
results.append(('each adjacent command swap rejected',len(p.COMMAND_SCHEDULE)-1))
for i in range(len(p.COMMAND_SCHEDULE)):
 r=T.process_fixture();c=r['commands'][i];c['expected_exit']=c['exit_code']=1-c['expected_exit']
 try:T.vp(r);raise AssertionError((i,'flipped expectation accepted'))
 except ValueError:pass
results.append(('each flipped expected exit rejected',len(p.COMMAND_SCHEDULE)))
report=json.loads(Path('build/takeover/multiterm-after-report-repair.json').read_text())
validate_commands(report['commands']);results.append(('real process command transcript',{'result':report['result'],'checks':report['check_count'],'commands':len(report['commands'])}))
for name in ('.ci/test_multiterm_process.py','.ci/validate_multiterm_report.py','.ci/test_multiterm_report.py'):
 results.append((name,hashlib.sha256(Path(name).read_bytes()).hexdigest()))
print(json.dumps(results,indent=2))
