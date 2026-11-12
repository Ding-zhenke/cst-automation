"""Bounded point-based RLC lumped elements, separate from face elements."""
import math
from cst_solver.expressions import validate_expression,validate_name


def _expression(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,str)):
        raise ValueError('Finite numeric value or CST expression required')
    if isinstance(value,float) and not math.isfinite(value): raise ValueError('Finite numeric value required')
    return validate_expression(str(value))


def point_lumped_command(name,*,r,l=0,c=0,p1,p2,folder=''):
    name=validate_name(name)
    if not isinstance(folder,str): raise ValueError('Folder must be a string')
    if folder: folder=validate_name(folder)
    if any(not isinstance(point,(list,tuple)) or len(point)!=3 for point in (p1,p2)):
        raise ValueError('Two explicit three-dimensional endpoints required')
    r,l,c=(_expression(value) for value in (r,l,c))
    p1=[_expression(value) for value in p1];p2=[_expression(value) for value in p2]
    lines=['With LumpedElement',' .Reset',f' .SetName "{name}"']
    if folder: lines.append(f' .Folder "{folder}"')
    lines+=[' .SetType "RLCSerial"',f' .SetR "{r}"',f' .SetL "{l}"',f' .SetC "{c}"',
            ' .SetP1 False, '+', '.join(f'"{v}"' for v in p1),
            ' .SetP2 False, '+', '.join(f'"{v}"' for v in p2),' .Create','End With']
    return '\n'.join(lines)


def validate_lumped_names(names):
    if not isinstance(names,list) or not 1<=len(names)<=1000:
        raise ValueError('Explicit bounded lumped-element names required')
    result=[validate_name(n) for n in names]
    if len({n.casefold() for n in result})!=len(result): raise ValueError('Unique element names required')
    return result


def read_lumped_elements(app,names):
    """Read native ByRef tuples; unsupported SDK bindings fail without guessing."""
    native=app.cst_file.model3d.LumpedElement;result={}
    for name in validate_lumped_names(names):
        coords=native.GetCoordinates(name)
        if not isinstance(coords,(tuple,list)) or len(coords)!=7 or coords[0] is not True:
            raise ValueError('Native lumped-element coordinates unavailable')
        props=native.GetProperties(name)
        if not isinstance(props,(tuple,list)) or len(props)!=9 or props[0] is not True or not isinstance(props[1],str):
            raise ValueError('Native lumped-element properties unavailable')
        numeric=list(coords[1:])+list(props[2:])
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in numeric):
            raise ValueError('Invalid native lumped-element numbers')
        result[name]={'start':list(coords[1:4]),'end':list(coords[4:7]),'coordinate_units':'project geometry units',
                      'properties':dict(zip(('type','resistance_ohms','inductance_h','capacitance_f',
                         'blocking_conductance','reverse_current','temperature_k','radius'),props[1:]))}
    return result


def read_lumped_elements_via_bridge(project,names,*,expected_project_path,receipt_root,confirm_idle=False):
    """Execute a fixed project-bound ByRef query on an already owned idle project."""
    import json
    from pathlib import Path
    from cst_automation.lumped_element_bridge import build_query,parse_receipt
    from cst_solver.native import execute_vba
    expected=Path(expected_project_path)
    if confirm_idle is not True or not expected.is_absolute() or Path(project.filename()).resolve()!=expected.resolve():
        raise ValueError('Explicit idle and exact owned project required')
    request=build_query(expected,validate_lumped_names(names),receipt_root=receipt_root)
    output=Path(request['output_path']);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise ValueError('Refusing existing receipt')
    manifest=output.with_suffix('.request.json')
    with manifest.open('x',encoding='utf-8') as stream:
        json.dump(request,stream,ensure_ascii=False,indent=2)
    execute_vba(project,request['vba_code'],target='model3d')
    if Path(project.filename()).resolve()!=expected.resolve(): raise ValueError('Project identity changed during query')
    report=parse_receipt(output.read_bytes(),request=request)
    report.update(artifact_path=str(output),manifest_path=str(manifest),idle_asserted_by_caller=True,idle_verified=False)
    return report
