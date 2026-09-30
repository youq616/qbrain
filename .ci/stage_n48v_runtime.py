"""Apply the three reviewed N48V integrations from exact base Git blobs.
This is NOT the refused PG test and does not touch any context/PG/delivery file.
Run in the dedicated feature branch; emits reversible runtime.patch and hashes.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import subprocess

BASE = 'e0a27f829d970c24ed8c566023ada0911c0042b3'
FILES = {
    'include/qbrain/core/brain.hpp': '5e32c31ff33c50984eccb866c801f5fdb8ad638d',
    'src/qbrain/core/brain.cpp': '032613c6920e7cebf2105f06ab65a290e03bf59f',
    'src/qbrain/ops/handlers.cpp': 'e7733c5f01f9fc5f5e0025b171f50dbd8996929f',
}
# The first assembler's published output, not a permissive arbitrary current tree.
FIRST_GENERATED = {
    'include/qbrain/core/brain.hpp': 'c57aafc312b1644520b2210cb3b75bb890ee590f',
    'src/qbrain/core/brain.cpp': '3a444be87edaaae354870c7d61f48e03c7e715f8',
    'src/qbrain/ops/handlers.cpp': 'ff17ed2acdb01397c61701c6311f1bfa66f3aa7f',
}

def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('exact source anchor count mismatch')
    return text.replace(old, new)

def main(output):
    output.mkdir(parents=True, exist_ok=False)
    updates = {}; records = []; patch = []
    for name, expected in FILES.items():
        raw = subprocess.check_output(['git', 'show', BASE + ':' + name])
        if blob(raw) != expected:
            raise ValueError('base Git blob mismatch: ' + name)
        original = raw.decode('utf8'); changed = original
        if name.endswith('brain.hpp'):
            changed = replace(changed, '#include "qbrain/storage/database.hpp"\n',
                '#include "qbrain/storage/database.hpp"\n#include "qbrain/ai/query_embedding_cache.hpp"\n')
            changed = replace(changed, '#include <cstddef>\n', '#include <cstddef>\n#include <memory>\n')
            changed = replace(changed, '  Config& config() { return config_; }\n',
                '  Config& config() { return config_; }\n'
                '  ai::QueryEmbeddingCache& query_embedding_cache() {\n'
                '    if (!query_embeddings_) query_embeddings_ = std::make_unique<ai::QueryEmbeddingCache>();\n'
                '    return *query_embeddings_;\n'
                '  }\n')
            changed = replace(changed, '  Config config_;\n',
                '  Config config_;\n  std::unique_ptr<ai::QueryEmbeddingCache> query_embeddings_;\n')
        elif name.endswith('brain.cpp'):
            for anchor in ['void Brain::open_at(const std::string& db_path) {\n',
                           'void Brain::open_pg(const std::string& dsn) {\n',
                           'void Brain::close() {\n', 'void Brain::load_config() {\n']:
                changed = replace(changed, anchor, anchor + '  if (query_embeddings_) query_embeddings_->clear();\n')
        else:
            changed = replace(changed, '#include "qbrain/ai/embed.hpp"\n',
                '#include "qbrain/ai/embed.hpp"\n#include "qbrain/ai/query_embedding.hpp"\n')
            changed = replace(changed, 'auto er = ai::embed_texts(ctx.brain->config(), {q});',
                'auto er = ai::query_embedding(*ctx.brain, q, opts.source_id);', 2)
        result = changed.encode('utf8')
        head_bytes = subprocess.check_output(['git', 'show', 'HEAD:' + name])
        if head_bytes not in (raw, result) and blob(head_bytes) != FIRST_GENERATED[name]:
            raise ValueError('refuse unrelated current content: ' + name)
        working = Path(name).read_bytes()
        if working != head_bytes:
            raise ValueError('refuse uncommitted source edits: ' + name)
        updates[name] = result
        patch.extend(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                        'a/' + name, 'b/' + name))
        records.append(dict(path=name, before_blob=expected, actual_previous_blob=blob(head_bytes),
                            after_blob=blob(result), sha256=hashlib.sha256(result).hexdigest()))
    for name, raw in updates.items():
        Path(name).write_bytes(raw)
    (output / 'runtime.patch').write_text(''.join(patch), encoding='utf8', newline='')
    (output / 'integration.json').write_text(json.dumps(dict(base=BASE, files=records), indent=2), encoding='utf8')
    print(json.dumps(dict(base=BASE, files=records)))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args().output)
