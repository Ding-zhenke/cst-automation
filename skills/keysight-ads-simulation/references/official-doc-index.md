# ADS 2026 Update 1 official documentation index

Use this index for the locally installed, offline Keysight documentation. The validated installation is:

- ADS root: `D:\Program Files\Keysight\ADS2026_Update1`
- Product: Advanced Design System 2026 Update 1
- Design Environment API: 635
- ADS Python: CPython 3.13.2

Substitute `%HPEESOF_DIR%` for the installation root in reusable commands. Prefer these local pages over web summaries because they match the installed binaries and API.

## Python API overview

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\pythonapi\Python_API.html`
  - Entry point for Design Environment, Dataset, Data Display, AEL bridge, and EDA Toolbox APIs.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\relnotes\ADS_2026_Update_1.0_Release_Notes.html`
  - ADS 2026 Update 1 changes, including the officially released Data Display Python API.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\relnotes\ADS_2026_Release_Notes.html`
  - Base ADS 2026 changes and known issues.

## Design Environment API

- `%HPEESOF_DIR%\doc\python\de\html\index.html`
- `%HPEESOF_DIR%\doc\python\de\html\pydocs\intro\extension.html`
  - Running Python outside the ADS application and setting the environment.
- `%HPEESOF_DIR%\doc\python\de\html\pydocs\intro\embedded.html`
  - Embedded Python Console and application-mode behavior.
- `%HPEESOF_DIR%\doc\python\de\html\pydocs\intro\licensing.html`
- `%HPEESOF_DIR%\doc\python\de\html\pydocs\howto\newvenv.html`
- `%HPEESOF_DIR%\doc\python\de\html\pydocs\howto\existingvenv.html`
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\reference\de\index.html`
  - `create_workspace`, `open_workspace`, `close_workspace`, version, and application/automation state APIs.
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\examples\design_creation\ex_workspace.html`
  - Workspace creation and current-directory behavior.
- `%HPEESOF_DIR%\doc\python\de\examples\app\ex_create_sim_and_plot.py`
  - Official end-to-end example: create workspace/library/schematic, generate netlist, run, read a dataset, and plot.
- `%HPEESOF_DIR%\doc\python\de\examples\automation\ex_lpf.py`
  - Automation-mode design example.

## RF circuit-family routes

The following pages and archives were verified to exist under the validated ADS 2026 Update 1 root. Use them to confirm controller choices, component definitions, parameter names, and reference testbenches before automating a circuit family.

### Amplifier

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\dg\Amplifier_QuickStart_Guide.html`
  - Installed Amplifier DesignGuide entry and analysis sequence.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimsp\Example_-_Perform_S-Parameter_Simulation_on_a_Power_Amplifier_Circuit.html`
  - S-parameter setup for a biased amplifier.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimsp\Noise_Analysis_using_S-Parameter_Simulation.html`
  - Small-signal noise analysis associated with an S-parameter controller.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\expmeas\stab_fact().html`
  - Installed `stab_fact()` stability-factor measurement expression.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimgain\Performing_a_Gain_Compression_Simulation.html`
  - Gain-compression controller and analysis flow.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\examples\Large_Signal_Amplifier_Simulations.html`
  - Routes nonlinear amplifier measurements beyond the small-signal flow.
- `%HPEESOF_DIR%\examples\RF_Microwave\RFIC\amplifier_wrk.7zads`
  - Installed amplifier example workspace archive.
- `%HPEESOF_DIR%\examples\RF_Microwave\LNA_wrk.7zads`
- `%HPEESOF_DIR%\examples\RF_Microwave\MMIC\MMIC_LNA_wrk.7zads`
  - Installed LNA examples for general RF and MMIC workflows.
- `%HPEESOF_DIR%\examples\RF_Microwave\MMIC\MMIC_PA_wrk.7zads`
- `%HPEESOF_DIR%\examples\RF_Microwave\RF_Board\NADC_PA_wrk.7zads`
  - Installed MMIC and RF-board PA examples.

### Oscillator

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\dg\Oscillator_QuickStart_Guide.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\HB_Configuration_-_Oscillator.html`
  - Oscillator mode, `Freq[1]`, fundamental index, OscProbe, and OscPort configuration.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Harmonic_Balance_Simulation_for_Oscillator_Analyses.html`
  - OscProbe/OscPort placement and oscillator harmonic-balance workflow.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Oscillator_Phase_Noise_Analysis.html`
  - Phase-noise variables, sideband mixing, and interpretation.
- `%HPEESOF_DIR%\examples\RF_Microwave\LearnOsc_wrk.7zads`
  - Installed oscillator learning workspace archive.

### Filter

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimsp\Performing_a_S-Parameter_Simulation.html`
  - General S-parameter setup and sweep route for two-port filters and other networks.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\Using_LineCalc.html`
  - Installed LineCalc workflow for synthesizing and analyzing transmission-line dimensions.
- `%HPEESOF_DIR%\doc\python\de\examples\automation\ex_lpf.py`
  - Official low-pass-filter automation example.
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\examples\design_elements\ex_lpf.html`
  - Rendered Design Environment API example for the same filter family.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\appguide\Designing_a_Simple_Low_Pass_Filter.html`
  - Ideal/PDK schematic, synchronized layout, and Momentum comparison workflow.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\Example-_Designing_a_Microstrip_Filter.html`
  - Installed Momentum microstrip-filter example.

### RF switch

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsim\Parameter_Sweeps_and_Sweep_Plans.html`
  - Parameter and sweep-plan route for control/bias state coverage.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ccnld\PIN_diode.html`
  - Installed nonlinear PIN-diode component documentation for switch models.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\appguide\Designing_MMIC_SPDT_Switch.html`
  - Bias-state S-parameter behavior, layout synchronization, DRC/LVS, and EM model flow.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\appguide\MMIC_SPDT_Switch_Design.html`
- `%HPEESOF_DIR%\examples\RF_Microwave\MMIC\MMIC_SPDT_wrk.7zads`
  - Installed MMIC SPDT example workspace archive.

## Layout, technology, and substrate APIs

- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\examples\design_creation\ex_create_layout.html`
  - Official layout creation example.
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\examples\technology\ex_padstack.html`
  - Padstack creation and `add_via_with_specified_layers` example.
- `%HPEESOF_DIR%\doc\python\de\html\pysubst\docs\examples\ex_substrate_with_layout.html`
  - Substrate creation and layout binding example.
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\reference\de\db_uu\index.html#keysight.ads.de.db_uu.Design.add_via_with_specified_layers`
  - Explicit top/bottom PCBVia creation.
- `%HPEESOF_DIR%\doc\python\de\html\pypde\docs\reference\de\experimental\lpp.html#keysight.ads.de.experimental.lpp.LppDb`
  - Experimental `LppDb` layer-purpose-pair API; probe the installed version before use.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\usrguide\Padstack_Editor_GUI_Reference.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\Defining_Substrates_for_EM.html`

## LineCalc synthesis and AEL automation

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\Using_LineCalc.html`
  - Installed command-line and macro workflow, including `linecalc -m <file>.lcm`.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\LineCalc_AEL_Functions.html`
  - Installed AEL function index for unattended LineCalc setup and extraction.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\lcuiuser_synthesize().html`
  - Synthesize the unfixed physical or electrical LineCalc parameter.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\lcuiuser_set_physical_parms_fix().html`
  - Request the fixed state of a physical parameter; confirm the effective state in the saved native result.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\linecalc\lcuiuser_file_save_as_ok().html`
  - Save a native `.lcs` result to an explicit path after synthesis.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ccdist\CPWG_(Coplanar_Waveguide_with_Lower_Ground_Plane).html`
  - Installed CPWG model definition, parameters, equations, and documented model ranges.

## Schematic-to-layout and EM co-simulation

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\usrguide\Creating_a_Layout_from_a_Schematic.html`
  - Official schematic-to-layout generation and synchronization route.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\lvs\About_ADS_Layout_Versus_Schematic.html`
  - Layout-versus-schematic scope and comparison concepts.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\EM_Circuit_Cosimulation_Overview.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\Creating_and_Using_an_EM_Model_View.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\Performing_an_EM_Circuit_Cosimulation_with_an_EM_Model_View.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\em\Performing_an_EM_Circuit_Cosimulation_with_an_EM_Cosimulation_View.html`
  - Installed EM model/co-simulation view routes and hierarchy usage.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\examples\EM-Circuit_Co-Simulation_with_a_LTCC_low_pass_filter.html`
  - Example comparing a physical passive network in an EM-circuit flow.

## RFPro, Momentum, and xxpro

- `%HPEESOF_DIR%\doc\python\edatoolbox\html\API_Reference\xxpro\index.html`
  - `keysight.edatoolbox.xxpro` workspace and Pro view integration.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\rfpro\Creating_an_RFPro_View.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\rfpro\RFPro_Analysis.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\rfpro\Advanced_Simulator_Setup_for_Momentum_RF_and_Microwave.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\rfpro\Save_EM_Simulation_Results_in_Cellview.html`

## Gerber and Drill AEL APIs

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ael\Gerber_Functions.html`
  - `gbr_create_exporter`, export settings, `gbr_export_design`, `gbr_create_importer`, and `gbr_import_design`.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ael\Drill_Functions.html`
  - `drl_create_exporter`, export settings, and `drl_export_design`.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ael\gbr_export_design().html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\ael\drl_export_design().html`

## Design Verification Environment DRC

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\drc\DRC_Functions_(alphabetical).html`
  - DVE function index including `dve_create_drc_job`, `dve_job_run_drc`, and job-result accessors.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\drc\dve_job_set_rule_location_path().html`
  - Rule-location root used with a separate rule folder and rule file.
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\drc\dve_job_set_drc_rule_folder().html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\drc\dve_job_set_drc_rule_file().html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\drc\dve_job_run_drc().html`

## Circuit simulation and netlists

- `%HPEESOF_DIR%\doc\python\edatoolbox\html\API_Reference\ads\classes\circuit_simulator.html`
  - `CircuitSimulator`, `run`, and `run_netlist` parameters and return values.
- `%HPEESOF_DIR%\doc\python\edatoolbox\html\How-To\circuit_sim.html`
- `%HPEESOF_DIR%\doc\python\edatoolbox\html\Examples\ex_run_hb_simulation.html`
- `%HPEESOF_DIR%\doc\python\edatoolbox\html\Examples\ex_run_netlist.html`
- `%HPEESOF_DIR%\doc\python\edatoolbox\html\Examples\ex_run_netlist_from_disk.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsim\ADS_Simulator_Input_Syntax.html`
  - Simulator input syntax and direct `hpeesofsim` command-line fallback.

## Harmonic balance and mixer guidance

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\HB_Configuration_-_Frequencies.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Harmonic_Balance_Simulation_-_Basic_Setup.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Harmonic_Balance_Simulation_for_Mixer_Analyses.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Solve_Convergence_Problems.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\cktsimhb\Oversampling_to_Prevent_Aliasing.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\expsim\dbm()_Expression.html`
  - ADS voltage-to-dBm expression semantics.

## Dataset API

- `%HPEESOF_DIR%\doc\python\dataset\html\index.html`
- `%HPEESOF_DIR%\doc\python\dataset\html\concepts.html`
- `%HPEESOF_DIR%\doc\python\dataset\html\apidoc.html`
- `%HPEESOF_DIR%\doc\python\dataset\html\dependencies.html`
- `%HPEESOF_DIR%\doc\python\dataset\examples\create_dataset_from_dataframe.py`
- `%HPEESOF_DIR%\doc\python\dataset\examples\merge_dataframes.py`

## Data Display API

- `%HPEESOF_DIR%\doc\python\dds\html\index.html`
- `%HPEESOF_DIR%\doc\python\dds\html\intro\usage.html`
- `%HPEESOF_DIR%\doc\python\dds\html\intro\licensing.html`
- `%HPEESOF_DIR%\doc\python\dds\html\reference\dds\file.html`
- `%HPEESOF_DIR%\doc\python\dds\html\reference\dds\page.html`
- `%HPEESOF_DIR%\doc\python\dds\html\reference\dds\plots.html`
- `%HPEESOF_DIR%\doc\python\dds\html\reference\dds\trace.html`
- `%HPEESOF_DIR%\doc\python\dds\examples\simple.py`
- `%HPEESOF_DIR%\doc\python\dds\examples\modified_file.py`
- `%HPEESOF_DIR%\doc\python\dds\examples\expressions_and_dataframes.py`
- `%HPEESOF_DIR%\doc\python\dds\examples\print_to_pdf.py`

## AEL compatibility bridge

- `%HPEESOF_DIR%\doc\python\ael\html\intro\usage.html`
- `%HPEESOF_DIR%\doc\python\ael\html\concepts\ael_interoperability.html`
- `%HPEESOF_DIR%\doc\python\ael\html\reference\ael.html`

## Startup and licensing

- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\install\Using_Advanced_Design_System_after_Windows_Installation.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\license\License_Environment_Variables.html`
- `%HPEESOF_DIR%\doc\ads\Content\ads2026update1\license\Troubleshooting_License_Problems.html`

When an API signature or behavior is uncertain, open the corresponding local page or raw example rather than guessing from another ADS release.
