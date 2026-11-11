"""Offline builder/parser for documented CST task-port impedance ByRef getters."""
import math
import re
from pathlib import Path
from uuid import uuid4


def _quote(value):
    if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00'):
        raise ValueError('Nonempty single-line string required')
    return '"' + value.replace('"', '""') + '"'


def build_impedance_query(project_path, task_name, ports, *, receipt_root):
    project, root = Path(project_path), Path(receipt_root)
    if not project.is_absolute() or project.suffix.lower() != '.cst' or not root.is_absolute():
        raise ValueError('Absolute project and receipt root required')
    _quote(task_name)
    if (not isinstance(ports, list) or not 1 <= len(ports) <= 128
            or len(set(ports)) != len(ports)):
        raise ValueError('Explicit unique ports required')
    for port in ports: _quote(port)
    project, root = project.resolve(), root.resolve()
    resources = project.with_suffix(''); token = uuid4().hex
    output = root/(token+'.sp-impedance.txt')
    lines = ['Function HexText(ByVal text As String) As String',
             'Dim i As Long, value As String', 'value = ""', 'For i = 1 To Len(text)',
             'value = value & Right$("0000" & Hex$(AscW(Mid$(text, i, 1)) And &HFFFF&), 4)',
             'Next i', 'HexText = value', 'End Function', 'Sub Main',
             'Dim projectFolder As String, handle As Integer, zr As String, zi As String',
             'projectFolder = Replace(GetProjectPathName("Project"), "/", "\\")',
             'Do While Right$(projectFolder, 1) = "\\"',
             'projectFolder = Left$(projectFolder, Len(projectFolder) - 1)', 'Loop',
             f'If StrComp(projectFolder, {_quote(str(resources))}, vbTextCompare) <> 0 Then Err.Raise vbObjectError + 1, "SP", "Project mismatch"',
             f'If Dir$({_quote(str(output))}) <> "" Then Err.Raise vbObjectError + 2, "SP", "Receipt exists"',
             'With SimulationTask', ' .Reset', f' .Name {_quote(task_name)}',
             ' If Not .DoesExist Then Err.Raise vbObjectError + 3, "SP", "Task missing"',
             f' If LCase$(CStr(.GetTypeForTask({_quote(task_name)}))) <> "s-parameters" Then Err.Raise vbObjectError + 4, "SP", "Wrong task type"',
             ' handle = FreeFile', f' Open {_quote(str(output))} For Output As #handle',
             ' Print #handle, "CST_SP_IMPEDANCE_V1"', f' Print #handle, "request\t{token}"',
             ' Print #handle, "project\t" & HexText(projectFolder)',
             f' Print #handle, "task\t" & HexText({_quote(task_name)})',
             ' Print #handle, "unit\t" & HexText(CStr(.GetUnit("Resistance")))',
             f' Print #handle, "count\t{len(ports)}"']
    for port in ports:
        name = _quote(port)
        lines += [' zr = "": zi = ""', f' .GetConstPortImpedance {name}, zr, zi',
                  f' Print #handle, "port\t" & HexText({name}) & "\t" & HexText(CStr(.GetPortImpedanceType({name}))) & "\t" & HexText(CStr(.GetPortSourceType({name}))) & "\t" & HexText(zr) & "\t" & HexText(zi)']
    lines += [f' Print #handle, "END\t{token}"', ' Close #handle', 'End With', 'End Sub']
    return {'request_id': token, 'project_path': str(project), 'project_resources': str(resources),
            'task_name': task_name, 'ports': list(ports), 'output_path': str(output),
            'vba_code': '\n'.join(lines), 'schematic_identity_verified': False,
            'native_bridge_verified': False}


def parse_impedance_receipt(payload, *, request):
    if isinstance(payload, bytes): payload = payload.decode('ascii')
    if not isinstance(payload, str): raise ValueError('ASCII receipt required')
    lines = payload.splitlines(); ports = request['ports']; token = request['request_id']
    if len(lines) != len(ports)+7 or lines[0] != 'CST_SP_IMPEDANCE_V1' or lines[-1] != 'END\t'+token:
        raise ValueError('Incomplete or invalid receipt')
    def field(index, name):
        pieces = lines[index].split('\t')
        if len(pieces) != 2 or pieces[0] != name: raise ValueError('Invalid receipt field')
        return pieces[1]
    def unhex(value):
        if not re.fullmatch(r'(?:[0-9A-Fa-f]{4})+', value): raise ValueError('Invalid UTF16 hex')
        try: return bytes.fromhex(value).decode('utf-16-be')
        except UnicodeError as exc: raise ValueError('Invalid UTF16 text') from exc
    if (field(1, 'request') != token or Path(unhex(field(2, 'project'))).resolve() != Path(request['project_resources']).resolve()
            or unhex(field(3, 'task')) != request['task_name'] or unhex(field(4, 'unit')) != 'Ohm'
            or field(5, 'count') != str(len(ports))):
        raise ValueError('Receipt identity or unit differs')
    result = {}
    for line in lines[6:-1]:
        fields = line.split('\t')
        if len(fields) != 6 or fields[0] != 'port': raise ValueError('Invalid port row')
        name, mode, source, real, imag = [unhex(v) for v in fields[1:]]
        if name not in ports or name in result or mode != 'Constant' or source not in ('None', 'Signal'):
            raise ValueError('Wrong port or inactive constant impedance')
        try: r, i = float(real), float(imag)
        except ValueError as exc: raise ValueError('Numeric impedance required') from exc
        if not math.isfinite(r) or not math.isfinite(i) or r <= 0: raise ValueError('Invalid impedance')
        result[name] = {'real': r, 'imaginary': i, 'impedance_type': mode, 'source_type': source}
    if set(result) != set(ports): raise ValueError('Port coverage incomplete')
    return {'request_id': token, 'project_path': request['project_path'], 'task_name': request['task_name'],
            'ports': result, 'schematic_identity_verified': False,
            'native_bridge_verified': False, 'solver_verified': False}
