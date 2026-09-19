"""Score supplied task answer content offline. Never runs a client or model."""
import argparse
import json
import sys
from pathlib import Path
from memory_task_contract import decode, read, score, write_new


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('key', 'packet', 'answers', 'report'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    try:
        result = score(decode(read(a.key)), read(a.packet), decode(read(a.answers)))
        write_new(a.report, result)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'result': 'REJECTED', 'reason': 'invalid_input_or_output_not_new'}), file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in ('result', 'total', 'answered', 'correct', 'accuracy', 'host_consumption_verified')}))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
