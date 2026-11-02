"""Build only reviewed public files; never import CST or inspect private skills."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SKILLS = frozenset({
    'cst-sessions', 'cst-modeling', 'cst-simulation', 'cst-circuit',
    'cst-results', 'cst-diagnostics', 'cst-diode-loading',
    'cst-device-characterization', 'cst-figures',
})
MACHINE_PATH = re.compile(r'\b[A-Za-z]:[\\/]|/(?:Users|home|mnt|media|opt|tmp|var)/|\\\\[^\\\s]+\\')
PHYSICAL_LITERAL = re.compile(
    r'(?<![A-Za-z0-9_.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[ \t]*'
    r'(?:THz|GHz|MHz|kHz|Hz|dBm|mW|W|mV|V|mA|uA|μA|A|mm|um|μm|nm|ns|ps|us|μs|nH|pF|fF|Ohm|Ω)(?![A-Za-z0-9_])')
MODEL_VALUE = re.compile(r'\b(?:IS|CJO|TT|BV|IBV|VJ|RS)\s*[:=]\s*[+\-\d.]')
LINK = re.compile(r'!?\[[^\]]*\]\(([^)]+)\)')


def _relative(value):
    path = PurePosixPath(value)
    if (not value or '\\' in value or path.is_absolute()
            or any(part in ('.', '..') for part in path.parts)
            or ':' in value):
        raise ValueError('Package paths must be relative and contained')
    return path


def _public_text(name, content):
    text = content.decode('utf-8')
    if MACHINE_PATH.search(text):
        raise ValueError('Machine/private path in ' + name)
    if 'project-profile.md' in text or MODEL_VALUE.search(text):
        raise ValueError('Private project/model material in ' + name)
    if PHYSICAL_LITERAL.search(text):
        raise ValueError('Physical parameter literal requires public-content review: ' + name)
    return text


def validate_package(root, names):
    """Check standalone extracted files; return a small public validation summary."""
    root = Path(root).resolve()
    names = list(names)
    if len(names) != len(set(names)):
        raise ValueError('Duplicate package target')
    listed = set(names)
    entries = {PurePosixPath(n).parent.name for n in names if n.endswith('/SKILL.md')}
    if entries != SKILLS:
        raise ValueError('Skill set must be exactly the nine reviewed skills')
    for name in names:
        relative = _relative(name)
        source = root.joinpath(*relative.parts)
        resolved = source.resolve()
        if root not in resolved.parents or not source.is_file():
            raise ValueError('Missing or escaping package file: ' + name)
        text = _public_text(name, source.read_bytes())
        if name.endswith('/SKILL.md'):
            front = re.match(r'\A---\s*\n(.*?)\n---\s*\n', text, re.S)
            metadata = front.group(1) if front else ''
            matched = re.search(r'^name:\s*([a-z0-9-]+)\s*$', metadata, re.M)
            description = re.search(r'^description:\s*(.+)$', metadata, re.M)
            if (not matched or matched.group(1) != relative.parent.name
                    or not description or len(description.group(1)) > 1024):
                raise ValueError('Invalid skill metadata: ' + name)
        if name.endswith('.md'):
            for match in LINK.finditer(text):
                target = match.group(1).strip('<>')
                if target.startswith(('https://', 'http://', 'mailto:', '#')):
                    continue
                local = unquote(target.split('#', 1)[0])
                destination = (source.parent / local).resolve()
                if root not in destination.parents:
                    raise ValueError('Escaping link in ' + name)
                rel = destination.relative_to(root).as_posix()
                if rel not in listed or not destination.is_file():
                    raise ValueError('Missing package link in ' + name + ': ' + target)
    manifest = json.loads((root / 'plugin.json').read_text(encoding='utf-8'))
    compat = json.loads((root / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    if (manifest['name'] != 'cst-automation' or compat['name'] != manifest['name']
            or compat['version'] != manifest['version'] or compat['skills'] != './skills/'):
        raise ValueError('Inconsistent plugin identity')
    return {'skill_count': len(entries), 'files': len(names),
            'links': 'passed', 'public_content_checks': 'passed'}


def _archive(destination, files):
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            entry = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, content)


def build_plugin(root):
    root = Path(root).resolve()
    config = json.loads((root / 'plugins/cst-automation/package-files.json').read_text(encoding='utf-8'))
    if frozenset(config['skills']) != SKILLS or len(config['skills']) != len(SKILLS):
        raise ValueError('Skill declaration requires exactly nine unique entries')
    found = {p.parent.name for p in (root / 'skills').glob('*/SKILL.md')}
    if found != SKILLS:
        raise ValueError('Skill source set changed; review before packaging')
    files = {}
    for item in config['files']:
        relative = _relative(item['source'])
        target = _relative(item['target']).as_posix()
        source = root.joinpath(*relative.parts)
        resolved = source.resolve()
        if root not in resolved.parents or source.is_symlink() or not source.is_file():
            raise ValueError('Missing or escaping public source: ' + item['source'])
        if target in files:
            raise ValueError('Duplicate package target: ' + target)
        files[target] = source.read_bytes()
    output = root / 'dist'
    output.mkdir(exist_ok=True)
    destination = output / 'cst-automation-plugin.zip'
    market_destination = output / 'cst-automation-marketplace.zip'
    catalog = {'name': 'cst-automation-local',
               'interface': {'displayName': 'CST Automation Local'},
               'plugins': [{'name': 'cst-automation',
                            'source': {'source': 'local', 'path': './plugins/cst-automation'},
                            'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                            'category': 'Productivity'}]}
    with tempfile.TemporaryDirectory(prefix='plugin-build-', dir=output) as temporary:
        stage = Path(temporary)
        for name, content in files.items():
            target = stage / 'content' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        report = validate_package(stage / 'content', sorted(files))
        _archive(stage / destination.name, files)
        marketplace = {'plugins/cst-automation/' + n: b for n, b in files.items()}
        marketplace['.agents/plugins/marketplace.json'] = json.dumps(catalog, ensure_ascii=False, indent=2).encode('utf-8')
        _archive(stage / market_destination.name, marketplace)
        report['sha256'] = hashlib.sha256((stage / destination.name).read_bytes()).hexdigest()
        os.replace(stage / destination.name, destination)
        os.replace(stage / market_destination.name, market_destination)
        (output / 'plugin-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    print(build_plugin(Path(__file__).resolve().parents[1]))
