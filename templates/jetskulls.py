# JETSKULLS-CLI
import fcntl
import json
import os
import sys
from collections import defaultdict
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


CACHE_DIR = os.path.join(os.environ['HOME'], '.jetskulls')
IMAGE_PARENTS = 'image_parents'
LOCK_FILE = 'lock'
DEFAULT_WEB_PORT = 6080


class SnapshotError(Exception):
    pass


class IdeError(Exception):
    pass


def download_file(url, save_dir):
    b_url = ensure_binary(url)
    name = sha256(b_url).hexdigest()
    file_path = os.path.join(save_dir, name)
    if os.path.isfile(file_path):
        return file_path

    try:
        check_call(['wget', '-O', file_path, url])
    except CalledProcessError:
        pass
    else:
        return file_path

    try:
        check_call(['curl', '-o', file_path, url])
    except CalledProcessError:
        os.remove(file_path)
        raise
    return file_path


class Ide(object):

    def __init__(self, ide_config, user_config, cache_dir):
        self._ide_config = ide_config
        self._user_config = user_config
        self._cache_dir = cache_dir
        self._lock_fd = None

    def _lock(self):
        file_path = os.path.join(self._cache_dir, LOCK_FILE)
        self._lock_fd = open(file_path, 'w')
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)

    def _unlock(self):
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        self._lock_fd.close()
        self._lock_fd = None

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

    def list_snapshots(self):
        cmd = r'docker images %s:* | tail +2 | awk "{print $2}"' % self._repo_name()
        output = check_output(cmd, shell=True)
        output = ensure_str(output).strip()
        if not output:
            return []
        return output.split('\n')

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

        self._lock()
        try:
            with open(pf, 'r') as fd:
                data = json.load(fd)
            data[snapshot_name] = parent_snapshot
            content = json.dumps(data, indent=1)
            with open(pf, 'w') as fd:
                fd.write(content)
        finally:
            self._unlock()

    def remove_snapshot(self, snapshot_name):
        pf = self._parents_file()
        running = self._running_image_tag()
        if running == snapshot_name:
            raise SnapshotError('Ide is running on this snapshot, can not remove the snapshot!')

        self._lock()
        try:
            with open(pf, 'r') as fd:
                data = json.load(fd)
            for k_, v_ in data.items():
                if v_ == snapshot_name:
                    raise SnapshotError(
                        '%s is referenced by %s, can not remove it!' % (v_, k_))
        finally:
            self._unlock()

        cmd = ['docker', 'rmi', '-f', '%s:%s' % (self._repo_name(), snapshot_name)]
        check_call(cmd)

        self._lock()
        try:
            with open(pf, 'r') as fd:
                data = json.load(fd)
            data.pop(snapshot_name, None)
            content = json.dumps(data, indent=1)
            with open(pf, 'w') as fd:
                fd.write(content)
        finally:
            self._unlock()

    def start(self, snapshot_name):
        running = self._running_image_tag()
        if running and running != snapshot_name:
            raise IdeError('Ide is running on another snapshot[%s], stop the ide first.' % running)

        if running == snapshot_name:
            return

        cmd = [
            'docker', 'run', '-d',
            '--name', self._container_name(),
            '-v', '/dev/shm:/dev/shm',
            '-p', '%s:80' % self._user_config.get('web_port', DEFAULT_WEB_PORT),
        ]

        vnc_port = self._user_config.get('vnc_port')  # optional
        if vnc_port:
            cmd += ['-p', '%s:5900' % vnc_port]

        for item in self._user_config['mount'].strip().split(','):
            if ':' not in item:
                raise ValueError('Invalid mount map: %s' % item)
            cmd += ['-v', item]

        target_image = '%s:%s' % (self._repo_name(), snapshot_name)
        cmd.append(target_image)
        check_call(cmd)

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

    def build_ide(self, ide_type):
        ide_config = self._load_ide_config(ide_type)
        if 'v0' in Ide(ide_config, {}, self._cache_dir).list_snapshots():
            return

        file_path = download_file(ide_config['download'], self._cache_dir)
        ide_config['cache_file'] = file_path
        td = gettempdir()

        dockerfile = os.path.join(td, 'Dockerfile')
        with open(dockerfile, 'w') as fd:
            tp = jinja2.Template('templates/Dockerfile')
            content = tp.render(**ide_config)
            fd.write(content)

        image_name = 'jetskulls-%s:v0' % ide_type
        check_call(['docker', 'build', '-f', dockerfile, '-t', image_name, '.'])

    def get_ide(self, ide_type, user_config):
        ide_config = self._load_ide_config(ide_type)
        return Ide(ide_config, user_config, self._cache_dir)


def ide_ls(ide):
    pass


def ide_snapshot(ide):
    pass


def ide_start(ide):
    pass


def ide_stop(ide):
    pass


_ide_op_map = {
    'ls':       ide_ls,
    'snapshot': ide_snapshot,
    'start':    ide_start,
    'stop':     ide_stop,
}


def parse_and_run():
    if sys.argv[1] == 'build':
        ide_type = sys.argv[2]
        JetSkulls().build_ide(ide_type)
    else:
        ide_type = sys.argv[1]
        op = sys.argv[2]

        if op != 'start':
            ide = JetSkulls().get_ide(ide_type, {})
        else:
            args = sys.argv[3:]
            pairs, _ = getopt(args, '', ['web-port=', 'vnc-port=', 'mount='])
            arg_map = dict(pairs)
            user_config = {}
            if '--web-port' in arg_map:
                user_config['web_port'] = arg_map['--web-port']
            if '--vnc-port' in arg_map:
                user_config['vnc_port'] = arg_map['--vnc-port']
            if '--mount' not in arg_map:
                raise IndexError()
            user_config['mount'] = arg_map['--mount']
            ide = JetSkulls().get_ide(ide_type, user_config)

        func = _ide_op_map.get(op)
        if func is None:
            raise IndexError()

        func(ide)


if __name__ == '__main__':
    parse_and_run()
