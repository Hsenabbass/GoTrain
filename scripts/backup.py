"""Create/verify recovery snapshots and cache sealed dataset ZIPs; standard library only."""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request


def sha256(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


def stream_hash(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe recovery path')
    return path


def verify(archive):
    """Read regular backup members only; never execute or extract their contents."""
    with tarfile.open(archive, 'r:gz') as package:
        members = package.getmembers()
        if any(not member.isfile() for member in members):
            raise ValueError('Backup contains a link or other non-regular member')
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate backup member')
        for name in names:
            safe_name(name)
        manifest = json.load(package.extractfile('manifest.json'))
        expected = {'manifest.json'} | {'payload/' + name for name in manifest['files']}
        if set(names) != expected:
            raise ValueError('Backup members differ from manifest')
        for name, record in manifest['files'].items():
            safe_name(name)
            member = package.getmember('payload/' + name)
            if member.size != record['bytes'] or stream_hash(package.extractfile(member)) != record['sha256']:
                raise ValueError('Backup checksum/size mismatch: ' + name)
    return manifest


def create(root, includes):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], timeout=15)
    if git('status', '--porcelain').strip():
        raise ValueError('Commit source changes before creating a recovery snapshot')
    names = set(git('ls-files', '-z').decode().strip('\0').split('\0'))
    for include in includes:
        relative = safe_name(include)
        parts = relative.parts
        if len(parts) < 2 or parts[:2] not in (('artifacts', 'data-inspection'), ('artifacts', 'runs'), ('notebooks', 'saved')):
            raise ValueError('Include only reviewed data-inspection, completed runs, or notebooks/saved paths')
        source = root / relative
        if not source.exists():
            raise FileNotFoundError(include)
        if source.is_dir():
            names.update(str(path.relative_to(root)) for path in source.rglob('*') if not path.is_dir())
        else:
            names.add(str(relative))
    files = {}
    # This detects common accidental credentials, not every possible secret.
    secret = re.compile(rb'github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|X-Amz-Signature=[0-9a-f]{16,}|\.studio\.[a-z0-9-]+\.sagemaker\.aws')
    for name in sorted(names):
        relative = safe_name(name)
        path = root / relative
        if any(part.startswith('.') or part in ('credentials', 'github-credentials') for part in relative.parts) and name not in ('.gitignore', '.gitattributes'):
            raise ValueError('Private/hidden path requires exclusion: ' + name)
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('Backup source must be a regular file inside the repository')
        if path.suffix in ('.log', '.json', '.md', '.py', '.txt', '.ipynb'):
            with path.open('rb') as stream:
                tail = b''
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    if secret.search(tail + block):
                        raise ValueError('Potential secret/access URL in ' + name)
                    tail = block[-1024:]
        files[name] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    output = root / 'artifacts' / 'backups'
    output.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output).free < sum(f['bytes'] for f in files.values()) + 5 * 2**30:
        raise ValueError('Insufficient disk space plus 5 GiB reserve')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    manifest = {'created_utc': stamp, 'git_commit': git('rev-parse', 'HEAD').decode().strip(),
                'includes': includes, 'files': files}
    archive = output / (stamp + '-recovery.tar.gz')
    partial = archive.with_suffix('.partial')
    with tarfile.open(partial, 'w:gz', compresslevel=1) as package:
        for name in files:
            package.add(root / name, arcname='payload/' + name, recursive=False)
        data = json.dumps(manifest, indent=2).encode()
        member = tarfile.TarInfo('manifest.json')
        member.size = len(data)
        package.addfile(member, io.BytesIO(data))
    verify(partial)
    partial.rename(archive)
    checksum = sha256(archive)
    archive.with_name(archive.name + '.sha256').write_text(checksum + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': checksum, 'files': len(files), 'git_commit': manifest['git_commit']}))


def cache_data(root, destination):
    """Copy public immutable archives as opaque bytes; never inspect ZIP members."""
    record = json.loads((root / 'docs' / 'data-inspection.json').read_text())
    if record['repo'] != 'recursix/geo-bench-1.0' or not re.fullmatch('[0-9a-f]{40}', record['revision']):
        raise ValueError('Unexpected dataset source')
    expected = {'m-eurosat', 'm-brick-kiln', 'm-pv4ger-seg', 'm-chesapeake'}
    if {task['name'] for task in record['tasks']} != expected or len(record['tasks']) != 4:
        raise ValueError('Expected exactly the four selected tasks')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = []
    deadline = time.monotonic() + 900
    for task in record['tasks']:
        name = safe_name(task['benchmark'] + '/' + task['name'] + '.zip')
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256(target) != task['archive_sha256']:
            if shutil.disk_usage(destination).free < record['download_total_bytes'] - sum(item['bytes'] for item in records) + 5 * 2**30:
                raise ValueError('Insufficient space for dataset cache plus 5 GiB reserve')
            url = 'https://huggingface.co/datasets/' + record['repo'] + '/resolve/' + record['revision'] + '/' + str(name)
            temporary = target.with_suffix('.partial')
            # Public source only: no credentials, local execution, or sample decoding.
            with urllib.request.urlopen(url, timeout=30) as response, temporary.open('wb') as stream:
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    if time.monotonic() > deadline:
                        raise TimeoutError('Dataset cache exceeded 900 seconds')
                    stream.write(block)
            if sha256(temporary) != task['archive_sha256']:
                raise ValueError('Dataset archive checksum mismatch: ' + str(name))
            temporary.replace(target)
        records.append({'path': str(name), 'bytes': target.stat().st_size, 'sha256': task['archive_sha256']})
        print('VERIFIED', str(name), flush=True)
    (destination / 'manifest.json').write_text(json.dumps({'repo': record['repo'], 'revision': record['revision'], 'files': records}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    make = commands.add_parser('create')
    make.add_argument('--root', type=Path, default=Path.cwd())
    make.add_argument('--include', action='append')
    check = commands.add_parser('verify')
    check.add_argument('archive', type=Path)
    cache = commands.add_parser('cache-data')
    cache.add_argument('--root', type=Path, default=Path.cwd())
    cache.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'create':
        create(args.root.resolve(), args.include or ['artifacts/data-inspection'])
    elif args.command == 'verify':
        manifest = verify(args.archive)
        print(json.dumps({'verified_files': len(manifest['files']), 'git_commit': manifest['git_commit'], 'archive_sha256': sha256(args.archive)}))
    else:
        cache_data(args.root.resolve(), args.destination.resolve())


if __name__ == '__main__':
    main()
