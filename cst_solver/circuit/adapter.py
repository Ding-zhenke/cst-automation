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


def block_files(obj, kind):
    """GetFile is valid for intrinsic blocks; GetNumberOfFiles is not."""
    primary = str(obj.GetFile())
    if not primary:
        return []
    if kind.lower() in ("touchstone", "touchstone file"):
        return [str(obj.GetFilePath(i)) for i in range(int(obj.GetNumberOfFiles()))]
    return [primary]


def native_block_type(kind):
    return {'CircuitSemiconductor\\Diode': 'CircuitSemi\\Diode'}.get(kind, kind)


BERKELEY_DIODE_SCHEMA = {
    'Initial State': 'integer',
    **dict.fromkeys(('Relative Device Area', 'Temperature', 'Nominal temperature',
        'Saturation current temperature exponent', 'Saturation current', 'Emission coefficient',
        'Reverse breakdown voltage', 'Current at breakdown voltage',
        'Idealty factor for reverse breakdown', 'Zero-bias depletion capacitance',
        'Built-in junction potential', 'Junction grading coefficient', 'Transit time',
        'Series resistance'), 'double'),
}


def create_net(obj, name, endpoints):
    """CST creates an unnamed net, then permits renaming the generated name."""
    obj.Reset()
    generated = str(obj.AddComponentPorts('', endpoints, False))
    if not generated:
        raise CircuitError('circuit_build_partial', 'CST returned no created net name')
    if generated != name:
        obj.Rename(generated, name)
    obj.Apply()


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

    def property_readback(self, name):
        """Complete native property enumeration with actual strings and units."""
        obj = self.select('Block', name)
        obj.StartPropertyIteration()
        props, metadata = {}, {}
        for _ in range(10000):
            row = obj.GetNextProperty()
            if row == ('', '', ''):
                break
            if not isinstance(row, (tuple, list)) or len(row) != 3 or not all(isinstance(v, str) for v in row):
                raise CircuitError('circuit_result_read_failed', 'Invalid native property row')
            key, kind, value = row
            if not key or key in props:
                raise CircuitError('circuit_result_read_failed', 'Empty or duplicate native property', property=key)
            unit = obj.GetUnitForProperty(key)
            if not isinstance(unit, str):
                raise CircuitError('circuit_result_read_failed', 'Native property unit unreadable', property=key)
            props[key] = value
            metadata[key] = {'type': kind, 'unit': unit}
        else:
            raise CircuitError('circuit_result_read_failed', 'Native property iterator did not terminate')
        return {'properties': props, 'property_metadata': metadata}

    def diode_readback(self, name):
        """Identity from calibrated schema, never an echoed requested enum."""
        if str(self.select('Block', name).GetTypeName()) != 'Diode':
            raise CircuitError('circuit_result_read_failed', 'Not a calibrated intrinsic diode')
        actual = self.property_readback(name)
        if {key: item['type'] for key, item in actual['property_metadata'].items()} != BERKELEY_DIODE_SCHEMA:
            raise CircuitError('circuit_result_read_failed', 'Unsupported or incomplete intrinsic diode model schema')
        return {**actual,
                'model_identity': {'name': 'Berkeley SPICE', 'evidence': 'documented_native_property_schema'}}

    def spice_readback(self, name):
        obj = self.select('Block', name)
        if str(obj.GetTypeName()).lower() not in ('spice', 'spice block', 'spice file block'):
            raise CircuitError('circuit_result_read_failed', 'Not a native SPICE block')
        source_file = obj.GetFile()
        if not isinstance(source_file, str) or not source_file.strip():
            raise CircuitError('circuit_result_read_failed', 'Inline SPICE source readback is not calibrated')
        model, dialect = obj.GetSpiceModel(), obj.GetSpiceFilter()
        if not isinstance(model, str) or not model.strip() or not isinstance(dialect, str) or not dialect.strip():
            raise CircuitError('circuit_result_read_failed', 'SPICE model or dialect unreadable')
        return {**self.property_readback(name), 'spice_model': model, 'spice_filter': dialect}

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
            extra = {}
            if base == 'diode':
                actual = query(name + '.diode_model', lambda: self.diode_readback(name))
                if actual is not None:
                    props = actual['properties']
                    extra = {k: v for k, v in actual.items() if k != 'properties'}
            elif base in ('spice', 'spice block', 'spice file block'):
                actual = query(name + '.spice_model', lambda: self.spice_readback(name))
                if actual is not None:
                    props = actual['properties']
                    extra = {k: v for k, v in actual.items() if k != 'properties'}
            blocks.append({"name": name, "type": kind, "properties": props, **extra,
                           "pins": query(name + ".pins", lambda: self.pins(name)),
                           "files": query(name + ".files", lambda: block_files(obj, kind))})
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
        probes = query("probes", lambda: [{"name": n, "direction": "normal" if self.select("CircuitProbe", n).NormalDirection() else "reversed"}
                                          for n in list(iterate(self.schematic.CircuitProbe, "StartProbeNameIteration", "GetNextProbeName"))])
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
        kind = str(task.GetTypeForTask(name)).lower()
        props = {}
        if kind == "transient":
            props["circuit simulator"] = str(task.GetProperty("circuit simulator"))
        return {"name": name, "type": kind, "properties": props}

    def configure_transient_task(self, name, settings, *, create=False):
        """Common settings only. Recording interval is separate from integration."""
        import math
        task = self.select('SimulationTask', name)
        exists = bool(task.DoesExist())
        if create and exists:
            raise CircuitError('circuit_topology_invalid', 'Task name conflict; refusing overwrite', task_name=name)
        if not create and (not exists or str(task.GetTypeForTask(name)).lower() != 'transient'):
            raise CircuitError('circuit_topology_invalid', 'An existing transient task is required', task_name=name)
        dimensions = ['Time'] + (['Frequency'] if 'max_frequency_si' in settings else [])
        units = {d: str(self.schematic.Units.GetUnit(d)) for d in dimensions}
        factors = {}
        for dimension, unit in units.items():
            actual_dimension, factor = unit_info(unit)
            if actual_dimension != dimension:
                raise CircuitError('circuit_result_read_failed', 'Native task unit has wrong dimension')
            factors[dimension] = factor
        props = {'circuit simulator': 'cosimulation' if settings['mode'] == 'transient_cosim' else 'cst',
                 'tmax': format(settings['duration_si'] / factors['Time'], '.17g')}
        numeric = {'tmax'}
        if 'time_stepping' in settings:
            props['time stepping'] = settings['time_stepping']
        if 'requested_time_step_si' in settings:
            props['time step'] = format(settings['requested_time_step_si'] / factors['Time'], '.17g')
            numeric.add('time step')
        if 'minimum_time_step_si' in settings:
            props['minimum time step'] = format(settings['minimum_time_step_si'] / factors['Time'], '.17g')
            numeric.add('minimum time step')
        if 'integration_method' in settings:
            props['integration method'] = settings['integration_method']
        if 'integration_order' in settings:
            props['integration order'] = str(settings['integration_order'])
        if 'auto_solver' in settings:
            props['auto solver'] = 'TRUE' if settings['auto_solver'] else 'FALSE'
        if 'max_frequency_si' in settings:
            props.update({'fmax estimator': 'manual fmax', 'manual fmax': format(settings['max_frequency_si'] / factors['Frequency'], '.17g')})
            numeric.add('manual fmax')
        if 'accuracy' in settings:
            props['transient accuracy'] = format(settings['accuracy'], '.17g')
            numeric.add('transient accuracy')
        try:
            if create:
                task.Reset(); task.Type('transient'); task.Name(name); task.Create()
            for key, value in props.items():
                task.SetProperty(key, value)
            task.SetSweepData('0', props['tmax'], str(settings['output_points']))
            # SetSweepData resets Manual. Always set recording mode last.
            task.SetProperty('sampling method', settings['sampling_method'])
            props['sampling method'] = settings['sampling_method']
            actual = {key: task.GetProperty(key) for key in props}
            for key, expected in props.items():
                if key in numeric:
                    number = float(actual[key])
                    valid = math.isfinite(number) and number > 0 and math.isclose(number, float(expected), rel_tol=1e-10, abs_tol=0.)
                else:
                    valid = str(actual[key]).casefold() == expected.casefold()
                if not valid:
                    raise RuntimeError(f'Native task property did not match requested {key!r}')
            if any(str(self.schematic.Units.GetUnit(d)) != units[d] for d in dimensions):
                raise RuntimeError('Native task units changed during configuration')
        except Exception as exc:
            raise CircuitError('circuit_build_partial', f'Transient configuration write/readback failed: {exc}',
                               stage='configure_transient_task', task_name=name) from exc
        return {'task_name': name, 'created': create, 'readback': {'properties': actual, 'units': units},
                'requested_output_points': settings['output_points'], 'output_grid_readback': 'unsupported',
                'requested_time_step_si': settings.get('requested_time_step_si'),
                'internal_time_step_verified': False, 'readback_verified': False, 'solver_verified': False}

    def configure_task_ports(self, name, settings):
        from .configuration import configure_task_ports
        return configure_task_ports(self, name, settings)

    def configure_nonlinear_model(self, name, settings, *, create=False):
        from .configuration import configure_nonlinear_model
        return configure_nonlinear_model(self, name, settings, create=create)

    def properties(self, name, props, units, parameters=None):
        obj = self.select("Block", name)
        intrinsic_diode = str(obj.GetTypeName()) == 'Diode'
        diode_model = 'Model Type' in props and intrinsic_diode
        if diode_model and (type(props['Model Type']) is not int or props['Model Type'] != 2 or 'Model Type' in units):
            raise CircuitError('circuit_spec_invalid', 'Only intrinsic Berkeley SPICE model enum 2 is calibrated')
        values = {}
        ordered = list(props.items())
        if diode_model:
            ordered.sort(key=lambda item: item[0] != 'Model Type')
        for key, value in ordered:
            if key == 'Model Type' and diode_model:
                obj.SetIntegerProperty(key, str(value))
                actual = self.diode_readback(name)
                values[key] = {'requested_enum': value, 'model_identity': actual['model_identity']}
                continue
            if key in units:
                dim, _ = unit_info(units[key])
                number, _ = evaluate_quantity(value, units[key], parameters or {})
                if dim == 'Dimensionless':
                    if obj.GetUnitForProperty(key) != '':
                        raise CircuitError('circuit_spec_invalid', 'Native property is not dimensionless', property=key)
                else:
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
        if intrinsic_diode:
            actual = self.diode_readback(name)
            for key in values:
                if key != 'Model Type':
                    values[key] = actual['properties'][key]
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
            obj.Type(native_block_type(block["type"]))
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
            create_net(s.Net, net["name"], endpoints)
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
        from pathlib import Path
        path = Path(self.app.cst_file.filename()).resolve()
        logfile = path.with_suffix('') / 'Result' / 'DS' / 'Model.log'
        self._last_update = {'path': str(path), 'task_name': name,
                             'configuration': self.inspect(),
                             'prior_messages': self.app.get_messages(),
                             'log_path': str(logfile),
                             'log_before': logfile.read_text(encoding='utf-8-sig', errors='replace') if logfile.is_file() else ''}
        self._last_update['returned'] = False
        em_log = path.with_suffix('') / 'Result' / 'Model.log'
        self._last_update['em_log_before'] = em_log.read_text(encoding='utf-8-sig', errors='replace') if em_log.is_file() else ''
        em_output = path.with_suffix('') / 'Result' / 'output.txt'
        self._last_update['em_output_before'] = em_output.read_text(encoding='utf-8-sig', errors='replace') if em_output.is_file() else ''
        self.select("SimulationTask", name).ValidateSetup()
        self.select("SimulationTask", name).Update()
        self._last_update['returned'] = True

    def execution_evidence(self, task, token):
        from pathlib import Path
        from .evidence import log_completion, configuration_complete
        from .results import CircuitResult
        last = getattr(self, '_last_update', {})
        proof = {'completed': False, 'task_name': task, 'run_token': token,
                 'mode': 'network', 'circuit_runs': [], 'em_completed': False,
                 'reason': 'Fresh target log, unchanged input and saved task results required'}
        if not last.get('returned') or last.get('task_name') != task:
            return proof
        logfile = Path(last['log_path'])
        after = logfile.read_text(encoding='utf-8-sig', errors='replace') if logfile.is_file() else ''
        proof.update(log_completion(last['log_before'], after, task))
        proof['log_path'] = str(logfile)
        proof['prior_messages'] = last['prior_messages']
        current = self.inspect()
        proof['configuration_readable'] = configuration_complete(last['configuration']) and configuration_complete(current)
        proof['configuration_unchanged'] = proof['configuration_readable'] and last['configuration'] == current
        proof['project_unchanged'] = last['path'] == str(Path(self.app.cst_file.filename()).resolve())
        actual = self.task(task)
        if actual['type'] == 'transient' and actual['properties'].get('circuit simulator', '').lower() == 'cosimulation':
            from .evidence import cosim_evidence
            proof['mode'] = 'transient_cosim'
            proof.update(cosim_evidence(self.app, current, task, last))
            proof['completed'] = bool(proof['completed'] and proof['em_completed'])
        proof['completed'] = bool(proof['completed'] and proof['configuration_unchanged'] and proof['project_unchanged'])
        if proof['completed']:
            reader = CircuitResult(last['path'])
            # CST run 0 denotes this saved current state. Historical runs cannot
            # be attributed to the submitted input using this log alone.
            proof['circuit_runs'] = [{'tree_path': p, 'run_id': 0} for p in reader.get_tree_items(task_name=task)
                                     if 0 in reader.get_run_ids(p)]
            proof['completed'] = bool(proof['circuit_runs'])
            proof['reason'] = 'Selected task returned with fresh task-scoped completion log and saved result identities'
        return proof

    def dependencies(self):
        from .links import dependency_manifest
        return dependency_manifest(self.app.cst_file.filename(), self.inspect())

    def link_em(self, *, block_name, source, port_map, parameter_map):
        snapshot = self.inspect()
        if source == "self":
            candidates = [b for b in snapshot["blocks"] if b["name"] == block_name and b["type"].lower() in ("cstmws", "cst microwave studio", "cst microwave studio schematic block")]
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
