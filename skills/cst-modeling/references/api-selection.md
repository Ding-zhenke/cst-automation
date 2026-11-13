# API selection and geometry semantics

Before writing model history, inspect the installed `cst_solver.setup` method
and the explicit `tpc_service.sessions.model_api.METHODS` whitelist. Ordinary
imports and `inspect.signature` do not connect to CST. Record module location
and the methods actually used; a plugin version does not establish the Python
runtime version. Never instantiate setup just to discover its signatures.

| Operation | Existing Python methods |
|---|---|
| Brick, solid/hollow cylinder | `create_brick` / `square`, `create_cylinder` / `cylinder` |
| Sphere, cone/frustum, torus, elliptical cylinder | `create_sphere`, `create_cone`, `create_torus`, `create_elliptical_cylinder` |
| Triangular/hexagonal prism, wire | `create_triangular_prism`, `create_hexagonal_prism`, `create_wire` |
| Curve groups and profiles | `new_curve`, `create_polygon`, `create_polygon_3d`, `create_circle`, `create_rectangle_curve`, `create_line`, `create_arc`, `create_ellipse`, `create_spline` |
| Extrusion and profile operations | `extrude_curve`, `loft_curves`, `sweep_curve`, `cover_curve` |
| Boolean solids | `add`, `subtract`, `insert`, `intersect` (also `boolean_*` aliases) |
| Focused object edits | `rename_solid`, `change_component`, `delete_solid`, `delete_curve_item` |
| Transforms | `translate`, `rotation` / `rotate`, `mirror`, `scale`; ports use explicit `rotate_port` |
| Coordinates and picks | `set_wcs_basis`, `activate_global_wcs`, `reset_wcs`, `rotate_wcs`, `translate_wcs`, `pick_face`, `pick_edge`, `pick_clear` |
| Materials and assignments | `create_material_custom`, `create_material_tensor`, `create_material_full_tensor`, `create_material_gyrotropic`, `change_material` |
| Boundaries, ports, monitors | `boundary`, `set_background`, `create_waveguide_port_free`, `replace_port_with_waveguide`, `delete_port`, `rename_port`, `create_discrete_port`, `create_discrete_face_port`, `create_lumped_element`, `create_field_monitor`, `delete_field_monitor`, `create_probe` |

These names establish discoverability, not native validation of every command
in every CST version. Check signatures and relevant version evidence before use.
Port deletion and renumbering require the owning worker's `port-identity-edit-v1`
capability; preserve needed results and review the effects on connected objects.

## Non-obvious primitive conventions

`square(xmin,xmax,ymin,ymax,zmin,zmax,name,component,material)` is a **3D brick**,
not a planar square. Planar rectangles use `create_rectangle_curve`.

`cylinder(center,r,h,name,axis='z',component=...,material=...)` uses
`r=[outer_radius,inner_radius]`, with zero inner radius for a solid cylinder;
`h=[axis_min,axis_max]`, not center and height. The two transverse center
coordinates are `[x,y]` for z, `[x,z]` for y and `[y,z]` for x. Preserve symbolic
parameter expressions rather than freezing derived coordinates into literals.

`create_cone` starts at axis coordinate zero and ends at height; position it
explicitly with the coordinate system or a transform. `create_torus` uses
centerline major radius and tube minor radius; native outer/inner radii are
major+minor and major-minor. Check runtime for the corrected conversion.

Curve profiles belong to `curve:name`; solids belong to `component:name`.
Pass the requested curve group through profile creation and extrusion. Use
boolean subtraction for holes, not a solid cylinder mistaken for a void.
For parameterized transforms, name the actual object family; moving solids
does not move a port automatically. Specify asymmetric boundaries by face.

## Session routing and fallback

Use a reviewed `model_api` call batch with explicit project_id, stable stage_id,
and the digest of the canonical calls. Calls have method/args/kwargs fields;
inspect real signatures rather than guessing a common geometry schema.
For methods with log_flag, retain the executing default (1). log_flag=0 only
returns VBA text and creates nothing; session dispatch does not execute that text.

1. If Python method and session route exist, call them.
2. If only the route is missing, extend the static whitelist and signature
   tests, preserving the session-owned app. Do not open a second connection.
3. If a reusable operation has no wrapper, add a focused Python API, stub,
   offline command/validation tests and explicit route. Use installed official
   help or recorded commands to establish supported syntax.
4. Use bounded history only for a genuinely missing operation, naming that gap
   and its source evidence. Do not serialize a whole device as handwritten VBA
   for submission convenience. VBA generated **inside** an API is expected.

Domain geometry also needs its domain skill. When modeling TPC and its plugin
is available, load `topological-modeling` and relevant lattice/template skills;
they own lattice, phases and paths. Generic CST code must not import that domain.
An API inventory is not evidence of shape/material/port readback or a solve.
