"""Versioned circuit data validation. No CST access or third-party dependencies."""
import ast
import copy
import hashlib
import json
import math
import re


class CircuitSpecError(ValueError):
    code = "circuit_spec_invalid"


UNITS = {}
for dimension, base, prefixes in [
    ("Resistance", "Ohm", {"u": 1e-6, "m": 1e-3, "": 1, "k": 1e3, "M": 1e6}),
    ("Capacitance", "F", {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1}),
    ("Inductance", "H", {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1}),
    ("Frequency", "Hz", {"": 1, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}),
    ("Time", "s", {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1}),
    ("Voltage", "V", {"u": 1e-6, "m": 1e-3, "": 1, "k": 1e3}),
    ("Current", "A", {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1}),
    ("Length", "m", {"n": 1e-9, "u": 1e-6, "m": 1e-3, "c": 1e-2, "": 1}),
]:
    for prefix, factor in prefixes.items():
        UNITS[prefix + base] = (dimension, factor)
UNITS["1"] = ("Dimensionless", 1)
SI_UNITS = {dim: unit for unit, (dim, factor) in UNITS.items() if factor == 1}
PROPERTY_DIMENSIONS = {"Resistance": "Resistance", "Capacitance": "Capacitance",
                       "Inductance": "Inductance", "Voltage": "Voltage", "Current": "Current"}
BLOCK_TYPES = ("CircuitBasic\\Resistor", "CircuitBasic\\Capacitor", "CircuitBasic\\Inductor", "Ground",
               "CircuitSemi\\Diode", "CircuitSemiconductor\\Diode", "CSTMWS", "CSTMWSFile", "SPICE", "SPICEImport", "Touchstone")
TASK_TYPES = ("s-parameters", "dc", "ac", "transient")


def _require(condition, message):
    if not condition:
        raise CircuitSpecError(message)


def unit_info(unit):
    _require(isinstance(unit, str) and unit in UNITS, f"Unknown unit: {unit!r}")
    return UNITS[unit]


def spec_digest(spec):
    return hashlib.sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate_quantity(value, unit, parameters, stack=()):
    """Safe arithmetic with dimensions; returns SI value and dimension powers."""
    dim, factor = unit_info(unit)
    wanted = {} if dim == "Dimensionless" else {dim: 1}
    _require(not isinstance(value, bool), "Boolean is not a physical value")
    try:
        tree = ast.parse(str(value), mode="eval")
    except (ValueError, SyntaxError) as exc:
        raise CircuitSpecError(f"Invalid expression: {value!r}") from exc
    _require(len(list(ast.walk(tree))) <= 100, "Expression too complex")
    referenced = False

    def visit(node):
        nonlocal referenced
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            _require(math.isfinite(node.value), "Non-finite quantity")
            return float(node.value), {}
        if isinstance(node, ast.Name):
            referenced = True
            _require(node.id in parameters, f"Unknown parameter: {node.id}")
            _require(node.id not in stack, f"Cyclic parameter: {node.id}")
            parameter = parameters[node.id]
            _require(parameter.get("scope", "circuit") == "circuit", f"Cross-domain parameter: {node.id}")
            return evaluate_quantity(parameter["value"], parameter["unit"], parameters, stack + (node.id,))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            number, dimensions = visit(node.operand)
            return (-number if isinstance(node.op, ast.USub) else number), dimensions
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, ld = visit(node.left)
            right, rd = visit(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                _require(ld == rd, "Cannot add quantities of different dimensions")
                return (left + right if isinstance(node.op, ast.Add) else left - right), ld
            dimensions = dict(ld)
            sign = -1 if isinstance(node.op, ast.Div) else 1
            for key, power in rd.items():
                dimensions[key] = dimensions.get(key, 0) + sign * power
            dimensions = {k: v for k, v in dimensions.items() if v}
            _require(not isinstance(node.op, ast.Div) or right != 0, "Division by zero")
            return (left / right if sign == -1 else left * right), dimensions
        raise CircuitSpecError("Only declared parameters and + - * / arithmetic are allowed")

    number, dimensions = visit(tree.body)
    if not referenced:
        number, dimensions = number * factor, wanted
    _require(dimensions == wanted, f"Quantity dimension does not match {unit}")
    _require(math.isfinite(number), "Non-finite quantity")
    return number, dimensions


def validate_circuit_spec(spec):
    """Return a detached canonical spec; reject ambiguous electrical topology."""
    _require(isinstance(spec, dict), "Circuit spec must be a dictionary")
    allowed = {"schema_version", "units", "parameters", "blocks", "external_ports", "nets", "probes", "em_links", "tasks", "resolved_si"}
    _require(not set(spec) - allowed, f"Unknown spec keys: {set(spec) - allowed}")
    _require(type(spec.get("schema_version")) is int and spec["schema_version"] == 1, "schema_version must be integer 1")
    try:
        data = json.loads(json.dumps(spec, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise CircuitSpecError("Spec must contain finite JSON values") from exc
    data.setdefault("units", {})
    data.setdefault("parameters", {})
    _require(isinstance(data["units"], dict) and isinstance(data["parameters"], dict), "units/parameters must be mappings")
    for dimension, unit in data["units"].items():
        _require(unit_info(unit)[0] == dimension, f"Wrong unit for {dimension}")
    for group in ("blocks", "external_ports", "nets", "probes", "em_links", "tasks"):
        data.setdefault(group, [])
        _require(isinstance(data[group], list) and all(isinstance(x, dict) for x in data[group]), f"{group} must be an object list")
    resolved = {"parameters": {}, "blocks": {}}
    for name, parameter in data["parameters"].items():
        _require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None, "Invalid parameter identifier")
        _require(isinstance(parameter, dict) and "value" in parameter and "unit" in parameter, f"Parameter {name} needs value/unit")
        resolved["parameters"][name] = evaluate_quantity(parameter["value"], parameter["unit"], data["parameters"], (name,))[0]
    names = set()
    components = {}
    for group, kind in (("blocks", "Block"), ("external_ports", "ExternalPort"), ("probes", "Probe"), ("tasks", "Task")):
        for obj in data[group]:
            name = obj.get("name")
            _require(isinstance(name, str) and name.strip() and not any(c in name for c in '\r\n\x00'), f"Invalid {group} name")
            _require(name not in names, f"Duplicate name: {name}")
            names.add(name)
            components[(kind, name)] = obj
            if "position" in obj:
                pos = obj["position"]
                _require(isinstance(pos, list) and len(pos) == 2 and all(type(v) is int and 0 <= v <= 100000 for v in pos), "Position must be two layout-grid integers")
    for block in data["blocks"]:
        _require(not set(block) - {"name", "type", "properties", "property_units", "position", "rotation", "file", "spice_model"}, "Unknown block fields")
        _require(block.get("type") in BLOCK_TYPES, f"Unsupported block type: {block.get('type')}")
        if "rotation" in block:
            _require(type(block["rotation"]) is int and block["rotation"] % 90 == 0, "Block rotation must be a multiple of 90 degrees")
        if block["type"] in ("SPICEImport", "Touchstone", "CSTMWSFile"):
            _require(isinstance(block.get("file"), str) and block["file"], "File block needs explicit file")
        props, units = block.setdefault("properties", {}), block.setdefault("property_units", {})
        _require(isinstance(props, dict) and isinstance(units, dict), "properties/property_units must be mappings")
        _require(not set(units) - set(props), "Unit without corresponding property")
        resolved["blocks"][block["name"]] = {}
        for key, value in props.items():
            if key in PROPERTY_DIMENSIONS:
                _require(key in units and unit_info(units[key])[0] == PROPERTY_DIMENSIONS[key], f"Explicit correct unit required for {key}")
            if key in units:
                resolved["blocks"][block["name"]][key] = evaluate_quantity(value, units[key], data["parameters"])[0]
    linked_names = set()
    for link in data["em_links"]:
        _require(isinstance(link.get("block_name"), str) and link["block_name"], "EM link needs block_name")
        _require(link["block_name"] not in names and link["block_name"] not in linked_names, "Duplicate EM link/block name")
        _require(isinstance(link.get("source"), str) and link["source"], "EM link needs source")
        _require(isinstance(link.get("parameter_map"), dict), "EM link needs explicit parameter_map")
        mappings = link.get("port_map")
        _require(isinstance(mappings, list) and mappings, "EM link needs nonempty port_map")
        pins = set()
        for mapping in mappings:
            _require(isinstance(mapping, dict) and all(k in mapping for k in ("pin_name", "port_id", "mode", "reference", "polarity")), "Incomplete EM port mapping")
            _require(mapping["pin_name"] not in pins and mapping["polarity"] in (-1, 1), "Duplicate pin/invalid polarity")
            pins.add(mapping["pin_name"])
        linked_names.add(link["block_name"])
        components[("Block", link["block_name"])] = link
    occupied = set()
    net_names = set()
    for net in data["nets"]:
        _require(isinstance(net.get("name"), str) and net["name"] and net["name"] not in net_names, "Net names must be unique")
        net_names.add(net["name"])
        endpoints = net.get("endpoints", [])
        _require(len(endpoints) >= 2, "A net requires at least two endpoints")
        for endpoint in endpoints:
            _require(isinstance(endpoint, dict), "Endpoint must be an object")
            key = (endpoint.get("component_kind"), endpoint.get("component_name"))
            _require(key in components and key[0] in ("Block", "ExternalPort"), f"Unknown endpoint: {endpoint}")
            _require(isinstance(endpoint.get("pin_name"), str) and endpoint["pin_name"], "Pin name must be explicit")
            full = key + (endpoint["pin_name"],)
            _require(full not in occupied, f"Endpoint belongs to multiple nets: {full}")
            occupied.add(full)
    for probe in data["probes"]:
        endpoint = probe.get("endpoint", {})
        key = (endpoint.get("component_kind"), endpoint.get("component_name"), endpoint.get("pin_name"))
        _require(key in occupied, "Probe must reference a connected component pin")
        _require(type(probe.get("direction_inwards")) is bool, "Probe direction must be explicit")
    for task in data["tasks"]:
        _require(task.get("type") in TASK_TYPES, "Unsupported task type")
        _require(isinstance(task.setdefault("properties", {}), dict), "Task properties must be a mapping")
        if task["type"] == "s-parameters":
            _require(bool(data["external_ports"]), "S-parameter task needs external ports")
        external_names = {p["name"] for p in data["external_ports"]}
        excitations = task.get("excitations", {})
        _require(isinstance(excitations, dict), "excitations must be a mapping")
        for name, excitation in excitations.items():
            _require(name in external_names and isinstance(excitation, dict), "Excitation needs existing external port")
            _require(isinstance(excitation.get("type"), str) and isinstance(excitation.get("values"), list), "Excitation requires documented type/values")
    data["resolved_si"] = resolved
    return copy.deepcopy(data)
