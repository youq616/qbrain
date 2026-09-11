"""Exercise fail-closed deterministic packaging against the actual pinned artifact."""
from pathlib import Path
import sys
import tempfile
import json
from repack_verified_preview import repack

root=Path(sys.argv[1]).resolve()
archive=root/'artifact/qbrain-windows-x64-development.zip'
doc=root/'corrected.md'
evidence=root/'result.json'
checks=0
with tempfile.TemporaryDirectory() as td:
    t=Path(td)
    a=repack(archive,doc,evidence,t/'first.zip')
    b=repack(archive,doc,evidence,t/'second.zip')
    assert a['sha256']==b['sha256'];checks+=1
    variants=json.loads(evidence.read_bytes())
    (t/'alternative.json').write_text(json.dumps(dict(reversed(list(variants.items())))))
    c=repack(archive,doc,t/'alternative.json',t/'normalized.zip')
    assert a['sha256']==c['sha256'];checks+=1
    def rejected(fn,cls):
        global checks
        try: fn()
        except cls: checks+=1
        else: raise AssertionError('must reject')
    rejected(lambda:repack(archive,doc,evidence,t/'first.zip'),FileExistsError)
    (t/'wrong.zip').write_bytes(archive.read_bytes()+b'bad')
    rejected(lambda:repack(t/'wrong.zip',doc,evidence,t/'wrong-result.zip'),ValueError)
    variants['tested_source_commit']='0'*40
    (t/'bad.json').write_text(json.dumps(variants))
    rejected(lambda:repack(archive,doc,t/'bad.json',t/'mismatch.zip'),ValueError)
    (t/'bad.md').write_text('fake')
    rejected(lambda:repack(archive,t/'bad.md',evidence,t/'bad-doc.zip'),ValueError)
    assert not any((t/name).exists() for name in ['wrong-result.zip','mismatch.zip','bad-doc.zip']);checks+=1
print(f'Documentation-only preview repack: {checks} checks passed.')
