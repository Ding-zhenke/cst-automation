"""SDK-free contract for bounded discrete-port inspection."""
from .port_replacement import port_id

CAPABILITY = 'discrete-port-readback-v1'
LIMIT = 1000


def validate_ids(values):
    if not isinstance(values, list) or not 1 <= len(values) <= LIMIT:
        raise ValueError('discrete_port_ids must contain 1 to 1000 explicit IDs')
    ids = [port_id(value) for value in values]
    if len(set(ids)) != len(ids):
        raise ValueError('discrete_port_ids must be unique')
    return ids
