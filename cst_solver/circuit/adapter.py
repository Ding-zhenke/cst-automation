"""Native Design Studio boundary. Unknown SDK readback is never fabricated."""
from cst_automation.circuit_schema import SI_UNITS, evaluate_quantity, unit_info


class CircuitError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def iterate(obj, start, next_name):
    getattr(obj, start)()
    for _ in range(10000):
        name = getattr(obj, next_name)()
        if not name:
            return
        yield str(name)
    raise CircuitError("circuit_result_read_failed", "SDK iterator did not terminate")


class NativeAdapter:
    """Use documented schematic objects, with no unrestricted VBA entry point."""
    def __init__(self, app):
        self.app = app
        self.schematic = getattr(getattr(app, "cst_file", None), "schematic", None)
        if self.schematic is None:
            raise CircuitError("circuit_unavailable", "Project has no associated schematic")

    def select(self, kind, name):
        obj = getattr(self.schematic, kind)
        obj.Reset()
        obj.Name(name)
        return obj

    def endpoint(self, endpoint):
        kind, name, pin = endpoint
        if kind not in ("Block", "ExternalPort"):
            raise CircuitError("circuit_topology_invalid", "Unsupported endpoint kind", kind=kind)
        obj = self.select(kind, name)
        if kind == "Block":
            index = int(obj.GetPortIndex(pin))
        else:
            matches = [i for i in range(int(obj.GetNumberOfPorts())) if str(obj.GetPortName(i)) == pin]
            if len(matches) != 1:
                raise CircuitError("circuit_topology_invalid", "External pin not uniquely resolved", endpoint=endpoint)
            index = matches[0]
        if index < 0:
            raise CircuitError("circuit_topology_invalid", "Invalid port index", endpoint=endpoint)
        return [kind, name, index]

    def pins(self, name):
        obj = self.select("Block", name)
        ports = {str(obj.GetPortName(i)): i for i in range(int(obj.GetNumberOfPorts()))}
        return [{"pin_name": str(obj.GetPinName(i)), "pin_index": i,
                 "port_index": ports.get(str(obj.GetPinName(i))), "reference": "unknown", "mode": "unknown"}
                for i in range(int(obj.GetNumberOfPins()))]

    def inspect(self):
        unknown = []
        def query(label, fn):
            try:
                return fn()
            except Exception as exc:
                unknown.append({"field": label, "error": f"{type(exc).__name__}: {exc}"})
                return None
        units = {dim: query("units." + dim, lambda d=dim: str(self.schematic.Units.GetUnit(d)))
                 for dim in ("Frequency", "Time", "Resistance", "Capacitance", "Inductance", "Voltage", "Current")}
        block_obj = self.schematic.Block
        blocks = []
        for name in list(iterate(block_obj, "StartBlockNameIteration", "GetNextBlockName")):
            obj = self.select("Block", name)
            kind = str(obj.GetTypeName())
            props = {}
            base = kind.rsplit("\\", 1)[-1].lower()
            dimension = {"resistor": "Resistance", "capacitor": "Capacitance", "inductor": "Inductance"}.get(base)
            if dimension:
                props[dimension] = query(f"{name}.{dimension}", lambda: obj.GetProperty(dimension))
            blocks.append({"name": name, "type": kind, "properties": props,
                           "pins": query(name + ".pins", lambda: self.pins(name)),
                           "files": query(name + ".files", lambda: [str(obj.GetFilePath(i)) for i in range(int(obj.GetNumberOfFiles()))])})
        ports = []
        for name in list(iterate(self.schematic.ExternalPort, "StartPortNameIteration", "GetNextPortName")):
            obj = self.select("ExternalPort", name)
            ports.append({"name": name, "pins": [{"pin_name": str(obj.GetPortName(i)), "port_index": i}
                                                  for i in range(int(obj.GetNumberOfPorts()))]})
        nets = []
        def read_nets():
            obj = self.schematic.Net
            obj.Reset()
            for index in range(int(obj.GetNumberOfNets())):
                name = str(obj.GetNetNameByIndex(index))
                nets.append({"name": name, "subnets": [obj.GetComponentPorts(name, i) for i in range(int(obj.GetNumberOfSubnets(name)))]})
        query("nets", read_nets)
        probes = query("probes", lambda: [{"name": n, "direction": "unknown"} for n in iterate(self.schematic.CircuitProbe, "StartProbeNameIteration", "GetNextProbeName")])
        tasks = [self.task(n) for n in iterate(self.schematic.SimulationTask, "StartTaskNameIteration", "GetNextTaskName")]
        parameters = query("parameters", lambda: {str(self.schematic.GetParameterName(i)): str(self.schematic.GetParameterSValue(i))
                                                 for i in range(int(self.schematic.GetNumberOfParameters()))})
        return {"blocks": blocks, "external_ports": ports, "nets": nets, "probes": probes or [], "tasks": tasks,
                "units": units, "parameters": parameters, "unknown": unknown + [{"field": "parameter_dimensions", "status": "unknown"}],
                "evidence": "sdk_readback", "solver_verified": False}

    def task(self, name):
        task = self.select("SimulationTask", name)
        if not task.DoesExist():
            raise CircuitError("circuit_topology_invalid", "Task does not exist", task_name=name)
        kind = str(task.GetTypeForTask(name))
        props = {}
        if kind == "transient":
            props["circuit simulator"] = str(task.GetProperty("circuit simulator"))
        return {"name": name, "type": kind, "properties": props}

    def properties(self, name, props, units, parameters=None):
        obj = self.select("Block", name)
        values = {}
        for key, value in props.items():
            if key in units:
                dim, _ = unit_info(units[key])
                number, _ = evaluate_quantity(value, units[key], parameters or {})
                obj.SetLocalUnitForProperty(key, SI_UNITS[dim])
                # Freeze the safely evaluated SI value. Original expression remains in the spec/audit.
                obj.SetDoubleProperty(key, format(number, ".17g"))
            elif type(value) is bool:
                obj.SetBoolProperty(key, str(value))
            elif type(value) is int:
                obj.SetIntegerProperty(key, str(value))
            elif type(value) is float:
                obj.SetDoubleProperty(key, str(value))
            elif isinstance(value, str):
                obj.SetStringProperty(key, value)
            else:
                raise CircuitError("circuit_spec_invalid", "Unsupported property value", property=key)
            values[key] = obj.GetProperty(key)
        return values

    def apply(self, spec):
        s = self.schematic
        for dimension, unit in spec["units"].items():
            s.Units.SetUnit(dimension, unit)
        for name, number in spec["resolved_si"]["parameters"].items():
            if s.DoesParameterExist(name):
                raise CircuitError("circuit_topology_invalid", "Parameter already exists; refusing overwrite", parameter=name)
            s.StoreParameter(name, format(number, ".17g"))
        for link in spec["em_links"]:
            self.link_em(**link)
        for block in spec["blocks"]:
            obj = s.Block
            obj.Reset()
            obj.Type(block["type"])
            obj.Name(block["name"])
            if "position" in block:
                obj.Position(*block["position"])
            if "rotation" in block:
                obj.Rotate(block["rotation"])
            if "file" in block:
                from pathlib import Path
                path = Path(block["file"]).resolve()
                if not path.is_file():
                    raise CircuitError("circuit_dependency_missing", "Block model file missing", path=str(path))
                obj.SetFile(str(path))
            obj.Create()
            if "spice_model" in block:
                obj.SetSpiceModel(block["spice_model"])
            self.properties(block["name"], block["properties"], block["property_units"], spec["parameters"])
        for port in spec["external_ports"]:
            obj = s.ExternalPort
            obj.Reset()
            obj.Name(port["name"])
            if "position" in port:
                obj.Position(*port["position"])
            if "label" in port:
                obj.SetLabel(port["label"])
            obj.Create()
        for net in spec["nets"]:
            endpoints = [self.endpoint([p["component_kind"], p["component_name"], p["pin_name"]]) for p in net["endpoints"]]
            s.Net.Reset()
            s.Net.AddComponentPorts(net["name"], endpoints, False)
            s.Net.Apply()
        for probe in spec["probes"]:
            ep = probe["endpoint"]
            obj = s.CircuitProbe
            obj.Reset()
            obj.SetBlockPin("B" if ep["component_kind"] == "Block" else "P", ep["component_name"], ep["pin_name"], probe["direction_inwards"])
            obj.Name(probe["name"])
            obj.Create()
        for task in spec["tasks"]:
            obj = s.SimulationTask
            obj.Reset()
            obj.Type(task["type"])
            obj.Name(task["name"])
            obj.Create()
            for key, value in task["properties"].items():
                obj.SetProperty(key, str(value))
            for port_name, excitation in task.get("excitations", {}).items():
                obj.SetPortSignal(port_name, excitation["type"], [str(v) for v in excitation["values"]])

    def update_task(self, name):
        self.select("SimulationTask", name).Update()

    def execution_evidence(self, task, token):
        return {"status": "unknown", "reason": "Task.Update returned; task-specific completion/run identity requires live validation",
                "task_name": task, "run_token": token}

    def dependencies(self):
        from .links import dependency_manifest
        return dependency_manifest(self.app.cst_file.filename(), self.inspect())

    def link_em(self, *, block_name, source, port_map, parameter_map):
        snapshot = self.inspect()
        if source == "self":
            candidates = [b for b in snapshot["blocks"] if b["name"] == block_name and b["type"].lower() in ("cstmws", "cst microwave studio")]
            if len(candidates) != 1:
                raise CircuitError("circuit_topology_invalid", "Select the actual existing CSTMWS block; no duplicate self block will be created")
        else:
            from pathlib import Path
            path = Path(source).resolve()
            if not path.is_file():
                raise CircuitError("circuit_dependency_missing", "External CST project missing", path=str(path))
            if any(b["name"] == block_name for b in snapshot["blocks"]):
                raise CircuitError("circuit_topology_invalid", "External block name conflict")
            obj = self.schematic.Block
            obj.Reset()
            obj.Type("CSTMWSFile")
            obj.Name(block_name)
            obj.SetFile(str(path))
            obj.Create()
        pins = self.pins(block_name)
        by_name = {p["pin_name"]: p for p in pins}
        for mapping in port_map:
            if mapping.get("pin_name") not in by_name or by_name[mapping["pin_name"]]["port_index"] is None:
                raise CircuitError("circuit_topology_invalid", "EM pin is not a connectable port", mapping=mapping)
        return {"block_name": block_name, "source": source, "pins": pins, "requested_port_map": port_map,
                "requested_parameter_map": parameter_map, "verified": False,
                "reason": "3D port/mode/reference and parameter mapping readback requires live validation"}
