# JETSKULLS-CLI
import json
import os
import sys
from six import ensure_str
from collections import defaultdict
from subprocess import (
    check_output,
    CalledProcessError,
)


CACHE_DIR = os.path.join(os.environ['HOME'], '.jetskulls')
IMAGE_PARENTS = 'image_parents'


class SnapshotError(Exception):
    pass


class IdeError(Exception):
    pass


class Ide(object):

    def __init__(self, ide_config, user_config, cache_dir):
        self._ide_config = ide_config
        self._user_config = user_config
        self._cache_dir = cache_dir

    def _lock(self):
        pass

    def _unlock(self):
        pass

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
        output = ensure_str(output)
        return output.strip().split('\n')

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
        check_output(cmd)

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
        check_output(cmd)

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
            '-p', '%s:80' % self._user_config['web_port'],
        ]

        vnc_port = self._user_config.get('vnc_port')  # optional
        if vnc_port:
            cmd += ['-p', '%s:5900' % vnc_port]

        for item in self._user_config['user_mount'].strip().split(','):
            if ':' not in item:
                raise ValueError('Invalid mount map: %s' % item)
            cmd += ['-v', item]

        target_image = '%s:%s' % (self._repo_name(), snapshot_name)
        cmd.append(target_image)
        check_output(cmd)

    def stop(self):
        if not self._running_image_tag():
            return


class JetSkulls(object):

    def __init__(self, ide_configs, cache_dir=CACHE_DIR):
        self._ide_configs = ide_configs
        self._cache_dir = cache_dir

    def build_ide(self):
        pass

    def list_ides(self):
        pass

    def get_ide(self, ide_type):
        pass


def parse_args():
    pass


if __name__ == '__main__':
    pass
