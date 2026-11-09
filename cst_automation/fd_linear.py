"""Finite, typed FDSolver linear controls; no CST imports or execution."""


def linear_solver_code(settings):
    if not isinstance(settings, dict) or not settings or set(settings) - {
            'solver_type', 'limit_iterations', 'max_iterations'}:
        raise ValueError('Explicit supported linear solver settings required')
    if 'solver_type' in settings and settings['solver_type'] not in ('Auto', 'Iterative', 'Direct'):
        raise ValueError('solver_type must be Auto, Iterative or Direct')
    if 'limit_iterations' in settings and type(settings['limit_iterations']) is not bool:
        raise ValueError('limit_iterations must be boolean')
    if 'max_iterations' in settings:
        value = settings['max_iterations']
        if type(value) is not int or value <= 0 or settings.get('limit_iterations') is not True:
            raise ValueError('Positive integer max_iterations requires limit_iterations=True')
    if settings.get('limit_iterations') is True and 'max_iterations' not in settings:
        raise ValueError('Explicit max_iterations required when enabling a limit')
    commands = []
    if 'solver_type' in settings:
        commands.append(f' .Type "{settings["solver_type"]}"')
    if 'max_iterations' in settings:
        commands.append(f' .MaxIterations "{settings["max_iterations"]}"')
    if 'limit_iterations' in settings:
        commands.append(f' .LimitIterations "{settings["limit_iterations"]}"')
    return 'With FDSolver\n' + '\n'.join(commands) + '\nEnd With'
