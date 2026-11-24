# Hierarchical schematics and compact placement

Start from the existing workspace cells, symbols and models when available. Identify the port order, adjustable dimensions and model boundaries before choosing which cells to reuse. A simple standalone circuit can occupy one sheet. For a repeated or multi-block device, build the child definitions before placing them in their parent.

| View | What the reader should see |
| --- | --- |
| Testbench | Sources, terminations, the device, controller and measurements. On a bidirectional HB sheet, align the two excitation paths in rows with the same device orientation and label the driven ports. Group design variables by function and place goals with their optimizer. |
| Device or array | Compact symbols in physical signal order, RF ports at the ends and a separately traceable control or bias line. The static SP sheet can show the array directly when this helps the user edit it. |
| Reusable child | One editable electrical function per cell, such as a diode tap, a U-shaped interconnect or an RF/DC return. Show the tee at the actual branch node, the open/short termination and the order of the line sections. Draw U arms and bends in the routing direction. |

### Make the hierarchy editable

- Create a child schematic and matching symbol with the same numbered terminals. Place the symbol with `design.add_instance`. Wire to `inst_term_numbered(n).inst_pins[0].snap_point` after rotation or mirroring. Inspect the terminal nets at each boundary, including diode polarity and control/ground returns.
- Reuse one cell definition for repeated electrically identical units. Put adjustable dimensions on its instance interface. In ADS DE, register a subdesign `de.db.ModelDef` with typed `de.db.ModelParam` entries and persist the registration in the cell's `itemdef.py`. Use `instance.parameters` to set and read the parent bindings. Design-variable defaults alone do not expose those bindings.
- Connect shared, mirror-pair and independently adjustable dimensions according to the design. For example, the two outer diode taps can refer to the same length variable while the next pair refers to its own. Trace an edited variable through each intended instance to its leaf expression in the generated netlist.
- Put excitation, sweep and optimization settings on the appropriate testbench. When transferring manual SP dimensions to HB or layout, read the current values from the selected SP design and transfer the agreed geometry fields with units. Check HB-specific model, pump, bias, direction, sweep and controller settings against the HB baseline.

### Place and verify each sheet

1. Arrange symbols on a common signal axis. Keep the pitch short enough to follow a repeated chain and wide enough for the visible annotations. Route short orthogonal wires between neighboring pins. Place controls and grouped variables below or beside the signal path. Schematic drawing coordinates and physical dimensions have separate units.
2. Expose the parameters the user needs beside their instances. Show the child interface on module symbols. Inside a child, show line width and length, bend radius and angle, tee widths, model/file identity and the relevant expressions. In ADS 2026, set `instance.parameters[name].no_plot = False` for each selected parameter, give `db_uu.AnnotData(instance).max_rows` enough rows and pass that annotation object to `instance.update_item_annotation(...)`.
3. Check symbol bounds, wire segments, titles and `instance.bbox_annotation_only` with text visible. Move conflicting text with `instance.move_annotation((dx, dy))` or adjust local spacing. Check the fitted view of each requested sheet. When the user wants to see modules, open the saved editable views through the [desktop API](design-and-simulation.md#open-an-editable-schematic-in-desktop-ads). A requested dimension diagram should label the same ADS variables on their physical features.
4. For a reflow, compare the native netlists before and after, including child definitions, model references, numbered-terminal connectivity, parameter expressions and controllers. Account for generated net renaming by comparing connected terminals. Read back the saved parameter visibility as well. These checks cover different failure modes.
