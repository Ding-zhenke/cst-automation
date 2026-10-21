"""Public circuit facade, independent of SDK loading until an operation runs."""
from cst_automation.circuit_schema import validate_circuit_spec, BLOCK_TYPES, spec_digest
from .adapter import NativeAdapter, CircuitError


class CircuitAPI:
    def __init__(self, app, *, adapter=None):
        self.app = app
        self._adapter = adapter
        self._spec = None

    @property
    def adapter(self):
        if self._adapter is None:
            self._adapter = NativeAdapter(self.app)
        return self._adapter

    def capabilities(self, *, probe="static"):
        from .capabilities import circuit_capabilities
        return circuit_capabilities(probe=probe, app=self.app if probe == "live" else None)

    def inspect(self):
        return self.adapter.inspect()

    def list_block_types(self):
        return [{"type": name, "evidence": "documented_offline_adapter", "live_verified": False} for name in BLOCK_TYPES]

    def list_pins(self, block_name):
        block = next((b for b in self.inspect()["blocks"] if b["name"] == block_name), None)
        if block is None or block.get("pins") is None:
            raise CircuitError("circuit_topology_invalid", "Block pins unavailable", block_name=block_name)
        return block["pins"]

    def apply(self, spec, *, conflict="error"):
        if conflict != "error":
            raise CircuitError("circuit_spec_invalid", "Only conflict='error' is supported")
        data = validate_circuit_spec(spec)
        before = self.inspect()
        if data["parameters"]:
            existing_parameters = before.get("parameters")
            if existing_parameters is None:
                raise CircuitError("circuit_unavailable", "Parameter names could not be read; refusing parameter writes")
            if set(data["parameters"]) & set(existing_parameters):
                raise CircuitError("circuit_topology_invalid", "Parameter name conflict; no existing parameter overwritten")
        for group in ("blocks", "external_ports", "probes", "tasks", "nets"):
            existing = {obj["name"] for obj in before[group]}
            if any(obj["name"] in existing for obj in data[group]):
                raise CircuitError("circuit_topology_invalid", f"{group} name conflict")
        try:
            self.adapter.apply(data)
            after = self.inspect()
        except Exception as exc:
            raise CircuitError("circuit_build_partial", f"Circuit write/readback failed: {exc}", stage="apply", spec_digest=spec_digest(data)) from exc
        self._spec = data
        return {"applied": True, "spec_digest": spec_digest(data), "readback": after,
                "readback_verified": False, "solver_verified": False, "evidence": "configuration_readback_not_live_acceptance"}

    def set_properties(self, block_name, properties, *, units):
        block = next((b for b in self.inspect()["blocks"] if b["name"] == block_name), None)
        if block is None:
            raise CircuitError("circuit_topology_invalid", "Unknown block", block_name=block_name)
        parameters = (self._spec or {}).get("parameters", {})
        data = validate_circuit_spec({"schema_version": 1, "parameters": parameters,
                                      "blocks": [{"name": block_name, "type": next((t for t in BLOCK_TYPES if t.rsplit('\\', 1)[-1].lower() == block['type'].rsplit('\\', 1)[-1].lower()), block["type"]),
                                                  "properties": properties, "property_units": units}]})
        try:
            result = self.adapter.properties(block_name, properties, units, parameters=parameters) if isinstance(self.adapter, NativeAdapter) else self.adapter.properties(block_name, properties, units)
        finally:
            self._spec = None  # No verified cache remains after any attempted mutation.
        return {"block_name": block_name, "readback": result, "invalidated": "all_dependent_circuit_tasks", "resolved_si": data["resolved_si"]}

    def configure_transient_task(self, task_name, settings, *, create=False):
        from cst_automation.circuit_tasks import transient_settings
        data = transient_settings(settings)  # Invalid data must not load/access the SDK.
        if not isinstance(task_name, str) or not task_name.strip() or any(c in task_name for c in '\r\n\x00') or type(create) is not bool:
            raise CircuitError('circuit_spec_invalid', 'Explicit task name and boolean create required')
        self._spec = None
        try:
            return self.adapter.configure_transient_task(task_name, data, create=create)
        except CircuitError:
            raise
        except Exception as exc:
            raise CircuitError('circuit_build_partial', f'Transient configuration interrupted: {exc}',
                               stage='configure_transient_task', task_name=task_name) from exc

    def configure_task_ports(self, task_name, ports):
        from cst_automation.circuit_ports import task_port_settings
        from cst_automation.circuit_configuration import configuration_name
        configuration_name(task_name)
        data = task_port_settings(ports)
        self._spec = None
        try:
            return self.adapter.configure_task_ports(task_name, data)
        except CircuitError:
            raise
        except Exception as exc:
            raise CircuitError('circuit_build_partial', f'Port configuration interrupted: {exc}',
                               stage='configure_task_ports', task_name=task_name, requested=data) from exc

    def configure_nonlinear_model(self, block_name, settings, *, create=False):
        from cst_automation.circuit_models import nonlinear_model_settings
        from cst_automation.circuit_configuration import configuration_name, require
        configuration_name(block_name)
        require(type(create) is bool, 'create must be boolean')
        data = nonlinear_model_settings(settings)
        self._spec = None
        try:
            return self.adapter.configure_nonlinear_model(block_name, data, create=create)
        except CircuitError:
            raise
        except Exception as exc:
            raise CircuitError('circuit_build_partial', f'Model configuration interrupted: {exc}',
                               stage='configure_nonlinear_model', block_name=block_name, requested=data) from exc

    def validate(self, *, task_name):
        task = self.adapter.task(task_name)
        dependencies = self.inspect_dependencies()
        missing = [f for f in dependencies["files"] if not f.get("exists", False)]
        return {"ok": not missing and dependencies.get("complete") is True and not dependencies.get("unknown"), "task": task, "dependencies": dependencies,
                "unknown": dependencies.get("unknown", []), "solver_verified": False}

    def link_em(self, *, block_name, source, port_map, parameter_map):
        if not isinstance(port_map, list) or not port_map:
            raise CircuitError("circuit_spec_invalid", "Explicit nonempty port_map required")
        for entry in port_map:
            if not isinstance(entry, dict) or not all(k in entry for k in ("pin_name", "port_id", "mode", "reference", "polarity")) or entry["polarity"] not in (-1, 1):
                raise CircuitError("circuit_spec_invalid", "Each port map requires pin/port/mode/reference/polarity")
        if not isinstance(parameter_map, dict):
            raise CircuitError("circuit_spec_invalid", "parameter_map must be a mapping")
        self._spec = None
        return self.adapter.link_em(block_name=block_name, source=source, port_map=port_map, parameter_map=parameter_map)

    def inspect_dependencies(self):
        return self.adapter.dependencies()

    def bundle(self, destination):
        from .links import bundle_project
        self.app.save()
        return bundle_project(self.app.cst_file.filename(), self.inspect_dependencies(), destination)

    def run_checked(self, task_name, *, mode, expected_results, reuse="never", note=""):
        from .run import run_checked
        return run_checked(self, task_name, mode=mode, expected_results=expected_results, reuse=reuse, note=note)
