"""Sparse documented CST 2026 excitation and steady-state controls."""
import math

def commands(settings):
    if not isinstance(settings,dict) or not settings or set(settings)-{'excitation_port','excitation_mode','pulse_widths','steady_state_db','normalization_ohm','s_parameter_stop'}:
        raise ValueError('Explicit supported time-domain controls required')
    lines=[]
    for key,native in [('excitation_port','StimulationPort'),('excitation_mode','StimulationMode'),('pulse_widths','NumberOfPulseWidths')]:
        if key in settings:
            value=settings[key]
            if type(value) is not int or not 1<=value<=100000:raise ValueError(key+' must be a positive bounded integer')
            lines.append(f' .{native} "{value}"')
    if 'steady_state_db' in settings:
        value=settings['steady_state_db']
        if type(value) not in (int,float) or not math.isfinite(value) or not -80<=value<=0:raise ValueError('Invalid steady-state level')
        lines.append(f' .SteadyStateLimit "{value}"')
    if 'normalization_ohm' in settings:
        value=settings['normalization_ohm']
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('Positive reference impedance required')
        lines.extend([' .AutoNormImpedance "True"',f' .NormingImpedance "{value}"'])
    if 's_parameter_stop' in settings:
        stop=settings['s_parameter_stop']
        if not isinstance(stop,dict) or set(stop)!={'threshold','checks','frequency_range'}:raise ValueError('Explicit S-parameter stop settings required')
        threshold=stop['threshold'];checks=stop['checks'];band=stop['frequency_range']
        if type(threshold) not in (float,int) or not 0<threshold<1 or type(checks) is not int or not 1<=checks<=100:raise ValueError('Invalid S stop threshold/check count')
        if not isinstance(band,(list,tuple)) or len(band)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in band) or not 0<band[0]<band[1]:raise ValueError('Increasing finite frequency range required')
        text=','.join(format(v,'.15g') for v in band)
        lines.extend([' .RemoveAllStopCriteria',f' .AddStopCriterionWithTargetFrequency "All S-Parameters", "{threshold}", "{checks}", "True", "{text}"'])
    return 'With Solver\n'+'\n'.join(lines)+'\nEnd With'

def fd_excitation(port,mode):
    if type(port) is not int or type(mode) is not int or not 1<=port<=10000 or not 1<=mode<=10000:raise ValueError('Positive explicit port and mode required')
    return f'With FDSolver\n .Stimulation "{port}", "{mode}"\nEnd With'
