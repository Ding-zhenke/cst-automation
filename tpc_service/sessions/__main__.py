"""Local CLI. Recovery references are files, not global active-session settings."""
import argparse
import json
from pathlib import Path
import secrets
import sys

from .manager import SessionManager
from .store import lock, read, write


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit persistent CST conversation sessions')
    parser.add_argument('--root', required=True, help='Authorized absolute session root')
    parser.add_argument('--backend', choices=('cst', 'fake'), default='cst')
    parser.add_argument('--reference', required=True, help='Private absolute reference file for this conversation')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('ensure')
    sub.add_parser('status')
    sub.add_parser('resume')
    submit = sub.add_parser('submit')
    submit.add_argument('--request-id', required=True)
    submit.add_argument('--operation', required=True)
    submit.add_argument('--params-file', help='UTF-8 JSON file containing operation params')
    submit.add_argument('--operation-id')
    job = sub.add_parser('job')
    job.add_argument('--job-id', required=True)
    close = sub.add_parser('close')
    close.add_argument('--request-id', required=True)
    reconcile = sub.add_parser('reconcile')
    reconcile.add_argument('--review-file', required=True, help='JSON arguments from explicit human scene review')
    args = parser.parse_args(argv)
    try:
        reference = Path(args.reference)
        if not reference.is_absolute():
            raise ValueError('Reference path must be absolute')
        manager = SessionManager(args.root, backend=args.backend)
        if args.command == 'ensure':
            # Persist launch binding before ensure: retry can recover even if ensure reply is lost.
            with lock(reference.with_suffix(reference.suffix + '.lock')):
                value = read(reference)
                if value is None:
                    value = {'binding': 'conversation-' + secrets.token_hex(16),
                             'request_id': secrets.token_hex(16)}
                    write(reference, value)
                if 'session_id' not in value:
                    value.update(manager.ensure(value['binding'], value['request_id']))
                    write(reference, value)
            result = {'session_id': value['session_id'], 'reference': str(reference), 'started_cst': False}
        else:
            value = read(reference)
            if not value or value.get('root') != str(manager.root):
                raise ValueError('Reference is missing or belongs to a different root; run ensure with its original root')
            sid, credential = value['session_id'], value['credential']
            if args.command == 'status':
                result = manager.status(sid, credential)
            elif args.command == 'resume':
                result = manager.resume(sid, credential)
            elif args.command == 'job':
                result = manager.job(sid, credential, args.job_id)
            elif args.command == 'close':
                result = manager.close(sid, credential, args.request_id)
            elif args.command == 'reconcile':
                result = manager.reconcile(sid, credential, **read(args.review_file))
            else:
                params = read(args.params_file) if args.params_file else {}
                result = manager.submit(sid, credential, args.request_id, args.operation, params,
                                        operation_id=args.operation_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'error': getattr(exc, 'code', 'session_cli_failed'), 'message': str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
