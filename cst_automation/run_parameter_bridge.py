"""Documented VBA ByRef query transport. Builders/parser never call CST."""
import math
import re
from pathlib import Path
from uuid import uuid4


def _quote(text):
    value = str(text)
    if any(c in value for c in '\r\n\x00'):
        raise ValueError('Invalid VBA string')
    return '"' + value.replace('"', '""') + '"'


def prepare_run_parameter_query(project_path, result_id, *, receipt_root):
    """Generate one project-bound query, without writing or executing anything."""
    if not isinstance(result_id, str) or not re.fullmatch(r'Schematic:RunID:[1-9][0-9]*', result_id):
        raise ValueError('A fixed positive Schematic result ID is required')
    project, root = Path(project_path), Path(receipt_root)
    if not project.is_absolute() or project.suffix.lower() != '.cst' or not root.is_absolute():
        raise ValueError('Absolute CST project and receipt root are required')
    project, root = project.resolve(), root.resolve()
    token = uuid4().hex
    output = root / (token + '.runparams.txt')
    resources = project.with_suffix('')
    code = '\n'.join([
        'Function HexText(ByVal text As String) As String',
        'Dim i As Long, value As String', 'value = ""',
        'For i = 1 To Len(text)',
        'value = value & Right$("0000" & Hex$(AscW(Mid$(text, i, 1)) And &HFFFF&), 4)',
        'Next i', 'HexText = value', 'End Function',
        'Sub Main', 'Dim names As Variant, values As Variant, resolved As Boolean',
        'Dim projectFolder As String, handle As Integer, i As Long, count As Long',
        'projectFolder = Replace(GetProjectPathName("Project"), "/", "\\")',
        'Do While Right$(projectFolder, 1) = "\\"',
        'projectFolder = Left$(projectFolder, Len(projectFolder) - 1)', 'Loop',
        f'If StrComp(projectFolder, {_quote(resources)}, vbTextCompare) <> 0 Then Err.Raise vbObjectError + 1, "RunParameters", "Project mismatch"',
        f'If Dir$({_quote(output)}) <> "" Then Err.Raise vbObjectError + 2, "RunParameters", "Receipt already exists"',
        f'resolved = GetParameterCombination({_quote(result_id)}, names, values)',
        'count = 0', 'If resolved Then',
        'If Not IsArray(names) Or Not IsArray(values) Then Err.Raise vbObjectError + 3, "RunParameters", "Expected ByRef arrays"',
        'If LBound(names) <> LBound(values) Or UBound(names) <> UBound(values) Then Err.Raise vbObjectError + 4, "RunParameters", "Array length mismatch"',
        'count = UBound(values) - LBound(values) + 1',
        'If count < 1 Or count > 10000 Then Err.Raise vbObjectError + 5, "RunParameters", "Invalid parameter count"',
        'End If', 'handle = FreeFile', f'Open {_quote(output)} For Output As #handle',
        'Print #handle, "CST_RUN_PARAMETERS_V1"', f'Print #handle, "request\t{token}"',
        'Print #handle, "project\t" & HexText(projectFolder)',
        f'Print #handle, "result_id\t{result_id}"',
        'If resolved Then', 'Print #handle, "resolved\t1"', 'Else',
        'Print #handle, "resolved\t0"', 'End If',
        'Print #handle, "count\t" & Trim$(Str$(count))',
        'If resolved Then', 'For i = LBound(values) To UBound(values)',
        'Print #handle, "param\t" & HexText(CStr(names(i))) & "\t" & Trim$(Str$(CDbl(values(i))))',
        'Next i', 'End If', f'Print #handle, "END\t{token}"', 'Close #handle', 'End Sub'])
    return {'request_id': token, 'project_path': str(project), 'project_resources': str(resources),
            'result_id': result_id, 'output_path': str(output), 'vba_code': code,
            'native_bridge_verified': False}


def parse_run_parameter_receipt(payload, *, request):
    """Reject stale, wrong-project, incomplete or ambiguous native query data."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode('ascii')
        except UnicodeError as exc:
            raise ValueError('Receipt must use the ASCII/UTF16-hex transport') from exc
    if not isinstance(payload, str):
        raise ValueError('Receipt text is required')
    lines = payload.splitlines()
    if len(lines) < 7 or lines[0] != 'CST_RUN_PARAMETERS_V1':
        raise ValueError('Invalid receipt header')
    def field(index, name):
        pieces = lines[index].split('\t')
        if len(pieces) != 2 or pieces[0] != name:
            raise ValueError('Invalid receipt field: ' + name)
        return pieces[1]
    def unhex(value):
        if not value or not re.fullmatch(r'(?:[0-9A-Fa-f]{4})+', value):
            raise ValueError('Invalid UTF16 hex field')
        try:
            # Hex$(AscW(...)) emits each UTF-16 code unit most significant
            # digit first ("A" is 0041), not a little-endian byte stream.
            return bytes.fromhex(value).decode('utf-16-be')
        except UnicodeError as exc:
            raise ValueError('Invalid UTF16 value') from exc
    token = request['request_id']
    if field(1, 'request') != token or lines[-1] != 'END\t' + token:
        raise ValueError('Missing or stale request identity/footer')
    resources = unhex(field(2, 'project'))
    if not Path(resources).is_absolute() or Path(resources).resolve() != Path(request['project_resources']).resolve():
        raise ValueError('Native project identity mismatch')
    if field(3, 'result_id') != request['result_id'] or field(4, 'resolved') != '1':
        raise ValueError('Run not resolved or wrong result identity')
    count = field(5, 'count')
    if not re.fullmatch(r'[1-9][0-9]*', count) or int(count) > 10000 or len(lines) != int(count) + 7:
        raise ValueError('Invalid parameter count')
    parameters, seen = {}, set()
    for line in lines[6:-1]:
        parts = line.split('\t')
        if len(parts) != 3 or parts[0] != 'param':
            raise ValueError('Invalid parameter row')
        name = unhex(parts[1])
        if any(c in name for c in '\r\n\x00') or name.casefold() in seen:
            raise ValueError('Invalid or duplicate parameter name')
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?', parts[2]):
            raise ValueError('Invalid numeric parameter transport')
        value = float(parts[2])
        if not math.isfinite(value):
            raise ValueError('Non-finite parameter')
        parameters[name] = value
        seen.add(name.casefold())
    return {'result_id': request['result_id'], 'project_path': request['project_path'],
            'request_id': token, 'parameters': parameters, 'read_only': True,
            'native_bridge_verified': False, 'solver_verified': False}
