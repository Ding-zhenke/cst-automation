"""Read a bounded saved mesher-input snapshot, without any CST SDK access."""
import hashlib
import math
from pathlib import Path
import struct


def read_saved_options(path):
    path = Path(path)
    before = path.stat()
    if not 0 < before.st_size <= 100000:
        raise ValueError('Saved options size exceeds supported bound')
    with path.open('rb') as stream:
        data = stream.read(100001)
    with path.open('rb') as stream:
        repeated = stream.read(100001)
    after = path.stat()
    if (len(data) != before.st_size or data != repeated or
            (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
        raise ValueError('Saved options changed during reading')
    offset = 0

    def take(count):
        nonlocal offset
        if not 0 <= count <= len(data) - offset:
            raise ValueError('Truncated CBOR input')
        value = data[offset:offset+count]; offset += count
        return value

    def decode(depth=0):
        if depth >= 20:
            raise ValueError('CBOR nesting exceeds bound')
        tag = take(1)[0]; major, additional = tag >> 5, tag & 31
        if major == 7:
            if additional in (20, 21, 22):
                return {20: False, 21: True, 22: None}[additional]
            if additional not in (25, 26, 27):
                raise ValueError('Unsupported CBOR simple value')
            size, fmt = {25: (2, '>e'), 26: (4, '>f'), 27: (8, '>d')}[additional]
            value = struct.unpack(fmt, take(size))[0]
            if not math.isfinite(value):
                raise ValueError('Nonfinite CBOR value')
            return value
        if additional >= 28:
            raise ValueError('Indefinite or unsupported CBOR value')
        size = additional if additional < 24 else int.from_bytes(take(1 << (additional-24)), 'big')
        if major == 0:
            return size
        if major == 1:
            return -1-size
        if major == 3:
            return take(size).decode('utf-8')
        if major not in (4, 5) or size > len(data)-offset:
            raise ValueError('Unsupported or oversized CBOR container')
        if major == 4:
            return [decode(depth+1) for _ in range(size)]
        result = {}
        for _ in range(size):
            key = decode(depth+1)
            if not isinstance(key, str) or key in result:
                raise ValueError('Unsupported or duplicate CBOR map key')
            result[key] = decode(depth+1)
        return result

    value = decode()
    if offset != len(data) or not isinstance(value, dict) or not isinstance(value.get('Attributes'), dict):
        raise ValueError('Unsupported saved options structure or trailing input')
    return dict(source=str(path.resolve()), sha256=hashlib.sha256(data).hexdigest(),
                source_mtime_ns=after.st_mtime_ns, bytes=len(data), attributes=value['Attributes'],
                format=value.get('File Format'), version=value.get('File Version'),
                live_getter=False, source_job_binding='not_verified', mesh_convergence='not_assessed')
