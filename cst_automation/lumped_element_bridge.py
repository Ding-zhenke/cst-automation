"""Project-bound VBA ByRef query source and strict receipt parser; no CST import."""
import math
from pathlib import Path
from uuid import uuid4


def build_query(project_path,names,*,receipt_root):
    project=Path(project_path);root=Path(receipt_root)
    if not project.is_absolute() or not root.is_absolute() or not isinstance(names,list) or not 1<=len(names)<=1000:
        raise ValueError('Absolute project, receipt root and bounded names required')
    if (any(not isinstance(n,str) or not n.strip() or len(n)>128 or any(c in n for c in '"\r\n\x00') for n in names)
            or len({n.casefold() for n in names})!=len(names)):
        raise ValueError('Distinct safe element names required')
    token=uuid4().hex;output=root/(token+'.txt');path=str(output)
    if any(c in path for c in '"\r\n\x00'): raise ValueError('Invalid receipt path')
    lines=['Sub Main','Dim f As Integer','Dim kind As String','Dim x0 As Double, y0 As Double, z0 As Double',
           'Dim x1 As Double, y1 As Double, z1 As Double','Dim r As Double, l As Double, c As Double',
           'Dim gs As Double, i0 As Double, t As Double, radius As Double','f = FreeFile',
           f'Open "{path}" For Output As #f',f'Print #f, "CST_LUMPED_V1"',
           f'Print #f, "request" & vbTab & "{token}"',f'Print #f, "count" & vbTab & "{len(names)}"']
    numbers=('x0','y0','z0','x1','y1','z1','r','l','c','gs','i0','t','radius')
    for index,name in enumerate(names):
        lines += [f'If Not LumpedElement.GetCoordinates("{name}", x0, y0, z0, x1, y1, z1) Then Err.Raise 5',
                  f'If Not LumpedElement.GetProperties("{name}", kind, r, l, c, gs, i0, t, radius) Then Err.Raise 5',
                  f'Print #f, "item" & vbTab & "{index}" & vbTab & kind' + ''.join(' & vbTab & Trim$(Str$('+v+'))' for v in numbers)]
    lines += [f'Print #f, "END" & vbTab & "{token}"','Close #f','End Sub']
    return {'project_path':str(project.resolve()),'names':list(names),'request_id':token,
            'output_path':str(output.resolve()),'vba_code':'\n'.join(lines)}


def parse_receipt(raw,*,request):
    try: lines=raw.decode('ascii').splitlines()
    except (UnicodeDecodeError,AttributeError) as exc: raise ValueError('Invalid receipt encoding') from exc
    names=request['names'];token=request['request_id']
    if (len(lines)!=len(names)+4 or lines[:3]!=['CST_LUMPED_V1','request\t'+token,'count\t'+str(len(names))]
            or lines[-1]!='END\t'+token):
        raise ValueError('Incomplete or foreign lumped receipt')
    elements={}
    for index,line in enumerate(lines[3:-1]):
        fields=line.split('\t')
        if len(fields)!=16 or fields[0]!='item' or fields[1]!=str(index) or not fields[2]:
            raise ValueError('Invalid lumped receipt item')
        try: values=[float(v) for v in fields[3:]]
        except ValueError as exc: raise ValueError('Invalid lumped numeric value') from exc
        if not all(math.isfinite(v) for v in values): raise ValueError('Nonfinite lumped numeric value')
        elements[names[index]]={'start':values[:3],'end':values[3:6],'coordinate_units':'project geometry units',
            'properties':dict(zip(('type','resistance_ohms','inductance_h','capacitance_f','blocking_conductance',
                                  'reverse_current','temperature_k','radius'),[fields[2],*values[6:]]))}
    return {'elements':elements,'native_bridge_verified':False,'solver_verified':False}
