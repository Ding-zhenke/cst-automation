"""Public archive boundaries; no CST or global host configuration is accessed."""
import importlib.util
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'cst-sessions', 'cst-modeling', 'cst-simulation', 'cst-circuit',
    'cst-results', 'cst-diagnostics', 'cst-diode-loading',
    'cst-device-characterization', 'cst-figures',
}


def builder():
    source = ROOT / 'scripts/build_plugin.py'
    assert source.is_file(), 'A standalone public plugin builder is required'
    spec = importlib.util.spec_from_file_location('plugin_builder', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path):
    for name in ('skills', 'plugins'):
        if (ROOT / name).exists():
            shutil.copytree(ROOT / name, tmp_path / name)
    guide = ROOT / 'docs/guides/codex-plugin.md'
    if guide.exists():
        target = tmp_path / 'docs/guides/codex-plugin.md'
        target.parent.mkdir(parents=True)
        shutil.copyfile(guide, target)
    shutil.copyfile(ROOT / 'LICENSE', tmp_path / 'LICENSE')
    return tmp_path


def test_exact_nine_skills():
    assert {p.parent.name for p in (ROOT / 'skills').glob('*/SKILL.md')} == EXPECTED


def test_archive_is_standalone_explicit_and_reproducible(project):
    private = project / 'docs/private-notes.md'
    private.parent.mkdir(exist_ok=True)
    private.write_text('EXAMPLE_PRIVATE_PROJECT; bias = 12 V', encoding='utf-8')
    extra = project / 'skills/cst-diode-loading/references/project-profile.md'
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text('EXAMPLE_PRIVATE_PROJECT', encoding='utf-8')
    before = {str(p.relative_to(project)): p.read_bytes()
              for p in project.rglob('*') if p.is_file()}
    module = builder()
    archive = module.build_plugin(project)
    first = archive.read_bytes()
    assert module.build_plugin(project).read_bytes() == first
    with ZipFile(archive) as package:
        names = set(package.namelist())
        skills = {Path(n).parent.name for n in names if n.endswith('/SKILL.md')}
        assert skills == EXPECTED
        assert not any('project-profile' in n or 'private-notes' in n for n in names)
        assert b'EXAMPLE_PRIVATE_PROJECT' not in b''.join(package.read(n) for n in names)
        for manifest in ('plugin.json', '.codex-plugin/plugin.json'):
            assert json.loads(package.read(manifest))['name'] == 'cst-automation'
        unpacked = project / 'unpacked'
        package.extractall(unpacked)
        module.validate_package(unpacked, sorted(names))
    with ZipFile(project / 'dist/cst-automation-marketplace.zip') as market:
        catalog = json.loads(market.read('.agents/plugins/marketplace.json'))
        prefix = catalog['plugins'][0]['source']['path'].removeprefix('./') + '/'
        with ZipFile(archive) as package:
            for name in package.namelist():
                assert market.read(prefix + name) == package.read(name)
    assert all((project / name).read_bytes() == content for name, content in before.items())


@pytest.mark.parametrize('leak', [
    r'C:\Users\Example\private\model.cst',
    '/home/example/private/model.cst',
    'pump = 12 GHz',
    'bias = 12 V',
    '泵浦12GHz时使用该设置',
    'bias = .7 V',
    r'\\example-server\private\model.cst',
    'Read project-profile.md for the actual design.',
])
def test_listed_private_material_rejected_before_archive_replacement(project, leak):
    module = builder()
    archive = module.build_plugin(project)
    original = archive.read_bytes()
    source = project / 'skills/cst-diode-loading/SKILL.md'
    source.write_text(source.read_text(encoding='utf-8') + '\n' + leak, encoding='utf-8')
    with pytest.raises(ValueError, match='[Pp]rivate|[Pp]hysical|[Mm]achine'):
        module.build_plugin(project)
    assert archive.read_bytes() == original


def test_missing_and_escaping_links_are_rejected(project):
    module = builder()
    source = project / 'skills/cst-figures/SKILL.md'
    original = source.read_text(encoding='utf-8')
    for target in ('references/missing.md', '../../../outside.md'):
        source.write_text(original + '\n[bad](' + target + ')', encoding='utf-8')
        with pytest.raises(ValueError, match='[Ll]ink'):
            module.build_plugin(project)


def test_additional_skill_requires_explicit_review(project):
    directory = project / 'skills/unreviewed'
    directory.mkdir()
    (directory / 'SKILL.md').write_text('---\nname: unreviewed\ndescription: Unreviewed\n---\n')
    with pytest.raises(ValueError, match='[Ss]kill'):
        builder().build_plugin(project)


def test_study_reference_tracks_history_and_execution_contract():
    reference = ROOT / 'skills/cst-circuit/references/parameter-studies.md'
    assert reference.is_file()
    text = reference.read_text(encoding='utf-8')
    for contract in ('run_parameter_study', 'StudyResult', 'run_id=0',
                     'saved_readback_verified', 'reopen_verified', 'block/property'):
        assert contract in text


def test_shared_style_is_loadable():
    import matplotlib
    from matplotlib import rc_params_from_file
    style = ROOT / 'skills/cst-figures/assets/research.mplstyle'
    assert style.is_file()
    before = dict(matplotlib.rcParams)
    values = rc_params_from_file(str(style), use_default_template=False, fail_on_error=True)
    assert values['font.size'] == 10.5
    assert values['legend.frameon'] is False
    assert len(values['axes.prop_cycle']) >= 4
    assert dict(matplotlib.rcParams) == before
