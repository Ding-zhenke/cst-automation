"""Content-bound captions avoid CST's adjacent same-caption history replacement."""
import hashlib

CAPABILITY = 'content-bound-settings-history-v1'
METHODS = frozenset(('configure_tetrahedral_mesh', 'configure_fd_frequency',
                     'configure_fd_parallelization', 'configure_fd_linear_solver'))


def history_caption(stage, code):
    # Normalize line endings only: whitespace/string contents and order matter.
    normalized = code.replace('\r\n', '\n').replace('\r', '\n')
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f'{stage} [sha256:{digest}]'


def uses_settings_history(calls):
    return any(call.get('method') in METHODS for call in calls)
