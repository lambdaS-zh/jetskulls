# JETSKULLS-CLI
import fcntl
import json
import os
import sys
from functools import wraps
from getopt import (
    getopt,
    GetoptError,
)
from hashlib import sha256
from six import (
    ensure_str,
    ensure_binary,
)
from subprocess import (
    check_call,
    check_output,
    CalledProcessError,
)
from tempfile import gettempdir

import jinja2


CACHE_DIR = os.path.join('.', '.jetskulls')
IMAGE_PARENTS = 'image_parents'
LOCK_FILE = os.path.join(gettempdir(), 'jetskulls-lock')
INNER_SRC_DIR = '/root/Desktop/src'
DEFAULT_WEB_PORT = 6080
V0 = 'v0'


class SnapshotError(Exception):
    pass


class IdeError(Exception):
    pass


def download_file(url, save_dir):
    b_url = ensure_binary(url)
    name = sha256(b_url).hexdigest()
    file_path = os.path.join(save_dir, name)
    if os.path.isfile(file_path):
        return name

    try:
        check_call(['wget', '-O', file_path, url])
    except CalledProcessError:
        pass
    else:
        return name

    try:
        check_call(['curl', '-o', file_path, url])
    except CalledProcessError:
        os.remove(file_path)
        raise
    return name


class Lock(object):

    def __init__(self):
        self._fd = None

    def acquire(self):
        file_path = LOCK_FILE
        self._fd = open(file_path, 'w')
        fcntl.flock(self._fd, fcntl.LOCK_EX)

    def release(self):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()
        self._fd = None

    @classmethod
    def check(cls, func):

        @wraps(func)
        def _wrapped(*args, **kwargs):
            lock = cls()
            lock.acquire()
            try:
                return func(*args, **kwargs)
            finally:
                lock.release()

        return _wrapped


class Ide(object):

    def __init__(self, ide_config, cache_dir):
        self._ide_config = ide_config
        self._cache_dir = cache_dir

    def _repo_name(self):
        return 'jetskulls-%s' % self._ide_config['type']

    def _container_name(self):
        return 'jetskulls-%s-container' % self._ide_config['type']

    def _parents_file(self):
        return os.path.join(self._cache_dir, IMAGE_PARENTS)

    def _running_image_tag(self):
        try:
            cmd = ['docker', 'inspect', self._container_name(), '--format', '{{.Config.Image}}']
            output = check_output(cmd)
        except CalledProcessError:
            return ''

        output = ensure_str(output)
        return output.strip().split(':')[-1]

    def is_running(self):
        return bool(self._running_image_tag())

    def list_snapshots(self):
        cmd = r"docker images %s:* | tail +2 | awk '{print $2}'" % self._repo_name()
        output = check_output(cmd, shell=True)
        output = ensure_str(output).strip()
        if not output:
            return []
        return output.split('\n')

    @Lock.check
    def take_snapshot(self, snapshot_name):
        repo = self._repo_name()
        con = self._container_name()
        pf = self._parents_file()

        if snapshot_name in self.list_snapshots():
            raise SnapshotError('Snapshot_name %s is already used.' % snapshot_name)

        parent_snapshot = self._running_image_tag()
        if not parent_snapshot:
            raise SnapshotError('Not any ide running!')

        cmd = ['docker', 'commit', con, '%s:%s' % (repo, snapshot_name)]
        check_call(cmd)

        if not os.path.isfile(pf):
            data = {}
        else:
            with open(pf, 'r') as fd:
                data = json.load(fd)
        data[snapshot_name] = parent_snapshot
        content = json.dumps(data, indent=1)
        with open(pf, 'w') as fd:
            fd.write(content)

    @Lock.check
    def remove_snapshot(self, snapshot_name):
        pf = self._parents_file()
        running = self._running_image_tag()
        if running == snapshot_name:
            raise SnapshotError('Ide is running on this snapshot, can not remove the snapshot!')

        if not os.path.isfile(pf):
            data = {}
        else:
            with open(pf, 'r') as fd:
                data = json.load(fd)
        for k_, v_ in data.items():
            if v_ == snapshot_name:
                raise SnapshotError(
                    '%s is referenced by %s, can not remove it!' % (v_, k_))

        cmd = ['docker', 'rmi', '-f', '%s:%s' % (self._repo_name(), snapshot_name)]
        check_call(cmd)

        data.pop(snapshot_name, None)
        content = json.dumps(data, indent=1)
        with open(pf, 'w') as fd:
            fd.write(content)

    @Lock.check
    def start(self, snapshot_name, user_config):
        running = self._running_image_tag()
        if running and running != snapshot_name:
            raise IdeError('Ide is running on another snapshot[%s], stop the ide first.' % running)

        if running == snapshot_name:
            return

        cmd = [
            'docker', 'run', '-d',
            '--name', self._container_name(),
            '-v', '/dev/shm:/dev/shm',
            '-p', '%s:80' % user_config.get('web_port', DEFAULT_WEB_PORT),
        ]

        vnc_port = user_config.get('vnc_port')  # optional
        if vnc_port:
            cmd += ['-p', '%s:5900' % vnc_port]

        web_password = user_config.get('web_password')  # optional
        if web_password:
            cmd += ['-e', 'HTTP_PASSWORD=%s' % web_password]

        vnc_password = user_config.get('vnc_password')  # optional
        if vnc_password:
            cmd += ['-e', 'VNC_PASSWORD=%s' % vnc_password]

        mounts = user_config.get('mount')  # optional
        if mounts is None:
            src_dir = os.path.join(os.getcwd(), 'src', self._ide_config['type'])
            if not os.path.isdir(src_dir):
                os.makedirs(src_dir)
            mounts = '%s:%s' % (src_dir, INNER_SRC_DIR)
        for item in mounts.strip().split(','):
            if ':' not in item:
                raise ValueError('Invalid mount map: %s' % item)
            cmd += ['-v', item]

        target_image = '%s:%s' % (self._repo_name(), snapshot_name)
        cmd.append(target_image)
        check_call(cmd)

    @Lock.check
    def stop(self):
        if not self._running_image_tag():
            return
        check_call(['docker', 'rm', '-f', self._container_name()])


class JetSkulls(object):

    def __init__(self, cache_dir=CACHE_DIR):
        self._cache_dir = cache_dir

    @staticmethod
    def _load_ide_config(ide_type):
        file_name = '%s.json' % ide_type
        if not os.path.isfile(file_name):
            raise IdeError('Ide type %s not found!' % ide_type)
        with open(file_name, 'r') as fd:
            return json.load(fd)

    @Lock.check
    def build_ide(self, ide_type):
        ide_config = self._load_ide_config(ide_type)
        if V0 in Ide(ide_config, self._cache_dir).list_snapshots():
            return

        file_name = download_file(ide_config['download'], self._cache_dir)
        ide_config['cache_file'] = file_name

        dockerfile = 'Dockerfile'
        with open('templates/Dockerfile', 'r') as fd:
            tmpl_src = fd.read()
        with open(dockerfile, 'w') as fd:
            tp = jinja2.Template(tmpl_src)
            content = tp.render(**ide_config)
            fd.write(content)

        image_name = 'jetskulls-%s:%s' % (ide_type, V0)
        try:
            check_call(['docker', 'build', '-f', dockerfile, '-t', image_name, self._cache_dir])
        finally:
            os.remove(dockerfile)

    def get_ide(self, ide_type):
        ide_config = self._load_ide_config(ide_type)
        return Ide(ide_config, self._cache_dir)


def ide_ps(ide):
    if ide.is_running():
        print('ide is running.')
    else:
        print('ide is not running!')


def ide_ls(ide):
    for name in ide.list_snapshots():
        print(name)


def ide_snapshot(ide, snapshot_name):
    print('snapshotting...')
    ide.take_snapshot(snapshot_name)
    print('snapshot %s done.' % snapshot_name)


def ide_start(ide, snapshot_name, user_config):
    print('starting...')
    ide.start(snapshot_name, user_config)
    print('ide started from snapshot %s.' % snapshot_name)


def ide_stop(ide):
    print('stopping...')
    ide.stop()
    print('ide stopped.')


def build_ide(ide_type):
    print('building for %s...' % ide_type)
    JetSkulls().build_ide(ide_type)
    print('ide_type %s ready!' % ide_type)


def usage():
    head = sys.argv[0]
    sys.stderr.writelines([
        'Usage: \n',
        '  %s build <IDE-TYPE>                          build the first snapshot for some ide type.\n' % head,
        '                                               the first snapshot name will be "%s"\n\n' % V0,
        '  %s <IDE-TYPE> ls                             list snapshots of this ide type.\n\n' % head,
        '  %s <IDE-TYPE> ps                             check if ide is running.\n\n' % head,
        '  %s <IDE-TYPE> snapshot <SNAPSHOT-NAME>       take snapshot for current ide.\n\n' % head,
        '  %s <IDE-TYPE> start <ARGS> <SNAPSHOT-NAME>   start a ide from one snapshot.\n' % head,
        '    <ARGS> =\n'
        '    --web-port <PORT>          web port for user to view at. will be 6080 if omitted.\n',
        '    --web-password <PASSWORD>  can be omitted.\n',
        '    --vnc-port <PORT>          vnc port for user to view by vnc-viewer. wont be used if omitted.\n',
        '    --vnc-password <PASSWORD>  can be omitted.\n',
        '    --mount <PATH-MAPS>        this is the same as -v of docker run. will be src/<IDE-TYPE>/:%s if omitted. \n' % INNER_SRC_DIR,
        '                               use , to separate multiple maps. e.g. /dev:/dev,/home:/home:ro \n\n',
        '  %s <IDE-TYPE> stop                           stop current ide.\n\n' % head,
    ])


def parse_and_run():
    if sys.argv[1] == 'build':
        build_ide(sys.argv[2])
    else:
        ide_type = sys.argv[1]
        op = sys.argv[2]

        ide = JetSkulls().get_ide(ide_type)

        if op == 'ps':
            ide_ps(ide)
        elif op == 'ls':
            ide_ls(ide)
        elif op == 'snapshot':
            ide_snapshot(ide, sys.argv[3])
        elif op == 'stop':
            ide_stop(ide)
        elif op == 'start':
            args = sys.argv[3:]
            pairs, others = getopt(args, '', ['web-port=', 'web-password=', 'vnc-port=', 'vnc-password=', 'mount='])
            arg_map = dict(pairs)
            user_config = {}
            if '--web-port' in arg_map:
                user_config['web_port'] = arg_map['--web-port']
            if '--web-password' in arg_map:
                user_config['web_password'] = arg_map['--web-password']
            if '--vnc-port' in arg_map:
                user_config['vnc_port'] = arg_map['--vnc-port']
            if '--vnc-password' in arg_map:
                user_config['vnc_password'] = arg_map['--vnc-password']
            if '--mount' in arg_map:
                user_config['mount'] = arg_map['--mount']
            ide_start(ide, others[0], user_config)


if __name__ == '__main__':
    try:
        parse_and_run()
    except (IdeError, SnapshotError) as ex:
        sys.stderr.write(str(ex))
        sys.exit(1)
    except (IndexError, KeyError, GetoptError):
        usage()
        sys.exit(1)
