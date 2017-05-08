#!/usr/bin/env python
"""
Script to build Docker image of the project and possibly test it.

Actions are largely driven by environment variables, and some information
about the version of biweeklybudget installed...

If ``TRAVIS=="true"``:

  - build the image using the sdist created by ``tox``
  - run the image with test configuration and in-memory SQLite, make sure
    it serves pages (just check that ``GET /`` is 200 OK).

Otherwise:

  - just build the image
  - test it unless ``TEST_DOCKER=="false"``
  - tag it appropriately
  - if checked out to a git tag according to versionfinder, or
    ``DOCKER_BUILD_VER`` is set, build Docker image for that version
    **from PyPI**. Otherwise, build using the sdist created by ``tox``.

The latest version of this package is available at:
<http://github.com/jantman/biweeklybudget>

################################################################################
Copyright 2016 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of biweeklybudget, also known as biweeklybudget.

    biweeklybudget is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    biweeklybudget is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with biweeklybudget.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/biweeklybudget> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################
"""

import os
import sys
import logging
import time
from git import Repo
import requests
import docker
from io import BytesIO
import tarfile
from biweeklybudget.version import VERSION

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger()

for lname in ['versionfinder', 'pip', 'git', 'requests', 'docker']:
    l = logging.getLogger(lname)
    l.setLevel(logging.CRITICAL)
    l.propagate = True

DOCKERFILE_TEMPLATE = """
# biweeklybudget Dockerfile - http://github.com/jantman/biweeklybudget
FROM python:3.6.1

ARG version
USER root

COPY tini_0.14.0.deb /tmp/tini_0.14.0.deb
COPY requirements.txt /tmp/requirements.txt
COPY entrypoint.sh /tmp/entrypoint.sh
{copy}

RUN /usr/bin/dpkg -i /tmp/tini_0.14.0.deb
RUN /usr/local/bin/pip install virtualenv
RUN /usr/local/bin/virtualenv /app && \
    /app/bin/pip install -r /tmp/requirements.txt && \
    /app/bin/pip install {install} && \
    /app/bin/pip install gunicorn==19.7.1

# install phantomjs and locales; setip locales
RUN echo 'deb http://ftp.debian.org/debian jessie-backports main' >> \
    /etc/apt/sources.list && \
    apt-get update && \
    apt-get --assume-yes install phantomjs locales && \
    apt-get clean && \
    echo 'en_US.UTF-8 UTF-8' >> /etc/locale.gen && \
    /usr/sbin/locale-gen && \
    install -g root -o root -m 755 /tmp/entrypoint.sh /app/bin/entrypoint.sh

# default to using settings_example.py, and user can override as needed
ENV SETTINGS_MODULE=biweeklybudget.settings_example
ENV LANG=en_US.UTF-8

LABEL com.jasonantman.biweeklybudget.version=$version
LABEL maintainer "jason@jasonantman.com"
LABEL homepage "http://github.com/jantman/biweeklybudget"

EXPOSE 80
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/bin/entrypoint.sh"]
"""


class DockerImageBuilder(object):

    image_name = 'jantman/biweeklybudget'

    def __init__(self, toxinidir, distdir):
        """
        :param toxinidir: directory containing tox.ini
        :type toxinidir: str
        :param distdir: tox dist directory
        :type distdir: str
        """
        self._toxinidir = toxinidir
        self._distdir = distdir
        self._gitdir = os.path.join(self._toxinidir, '.git')
        logger.debug('Initializing DockerImageBuilder; toxinidir=%s gitdir=%s '
                     'distdir=%s',
                     self._toxinidir, self._gitdir, self._distdir)
        if not os.path.exists(self._gitdir) or not os.path.isdir(self._gitdir):
            raise RuntimeError(
                'Error: %s does not exist or is not a directory' % self._gitdir
            )
        logger.debug('Connecting to Docker')
        self._docker = docker.from_env()

    def _find_git_info(self):
        """
        Return information about the state of the Git repository tox is being
        run from.

        :return: dict with keys 'dirty' (bool), 'sha' (str), 'tag' (str or None)
        :rtype: dict
        """
        res = {}
        logger.debug('Checking git status...')
        repo = Repo(path=self._gitdir, search_parent_directories=False)
        res['sha'] = repo.head.commit.hexsha
        res['dirty'] = repo.is_dirty(untracked_files=True)
        res['tag'] = None
        for tag in repo.tags:
            # each is a git.Tag object
            if tag.commit.hexsha == res['sha']:
                res['tag'] = tag.name
        logger.debug('Git info: %s', res)
        return res

    def _tag_for_travis(self):
        """
        Return the Docker image tag for a TravisCI build.

        :rtype: str
        :return: tag for Docker image
        """
        job = os.environ.get('TRAVIS_JOB_NUMBER', '%d' % int(time.time()))
        return 'travis_%s' % job

    @property
    def build_ver(self):
        """
        Return the pypi version to build, or None if not a release build.

        :rtype: str
        :return: release build version or None
        """
        env_ver = os.environ.get('DOCKER_BUILD_VER', None)
        if env_ver is not None:
            logger.debug('build_ver %s based on DOCKER_BUILD_VER env var',
                         env_ver)
            return env_ver
        if self._gitinfo['tag'] is not None:
            logger.debug('build_ver %s based on git tag', self._gitinfo['tag'])
            return self._gitinfo['tag']
        return None

    def _tag_for_local(self):
        """
        Return the Docker image tag for a local build

        :return: tag for local build
        :rtype: str
        """
        time_s = '%d' % int(time.time())
        if self.build_ver is not None:
            tag = '%s_%s' % (self.build_ver, time_s)
            logger.debug('Local tag (build_ver): %s', tag)
            return tag
        sha = self._gitinfo['sha'][:8]
        if self._gitinfo['dirty']:
            sha += '-dirty'
        tag = '%s_%s' % (sha, time_s)
        logger.debug('Local tag: %s', tag)
        return tag

    def build(self):
        self._gitinfo = self._find_git_info()
        if os.environ.get('TRAVIS', 'false') == 'true':
            tag = self._tag_for_travis()
            logger.info('Travis build; tag=%s', tag)
        else:
            tag = self._tag_for_local()
            logger.info('Local build; tag=%s', tag)
        self._check_tag(tag)
        img_tag = self._build_image(tag)
        if self._needs_test:
            self.test(img_tag)
        logger.info('Image "%s" built and tested.', img_tag)
        if self.build_ver is not None:
            print("To push release image to Docker Hub:")
            print('docker push %s' % img_tag)
            print('docker tag %s %s:latest' % (img_tag, self.image_name))
            print('docker push %s:latest' % self.image_name)
        return img_tag

    @property
    def _needs_test(self):
        """
        Return True if image needs to be tested, False otherwise.

        :return: whether image should be tested
        :rtype: bool
        """
        if os.environ.get('TRAVIS', 'false') == 'true':
            return True
        if os.environ.get('TEST_DOCKER', 'true') == 'false':
            return False
        return True

    def test(self, tag):
        """
        Test the image that was just built.

        :param tag: tag of built image
        :type tag: str
        """
        db_container = self._run_mysql()
        dbname = db_container.name
        kwargs = {
            'detach': True,
            'name': 'biweeklybudget-test-%s' % int(time.time()),
            'environment': {
                'DB_CONNSTRING': 'mysql+pymysql://'
                    'root:root@mysql:3306/'
                    'budgetfoo?charset=utf8mb4'
            },
            'links': {dbname: 'mysql'},
            'ports': {
                '80/tcp': None
            }
        }
        img = '%s:%s' % (self.image_name, tag)
        logger.info('Docker run %s with kwargs: %s', img, kwargs)
        container = self._docker.containers.run(img, **kwargs)
        logger.info('Running biweeklybudget container; name=%s id=%s',
                    container.name, container.id)
        logger.info('Container status: %s', container.status)
        logger.info('Sleeping 20s for stabilization...')
        time.sleep(20)
        container.reload()
        logger.info('Container status: %s', container.status)
        if container.status != 'running':
            logger.critical('Container did not stay running! Logs:')
            logger.critical(
                container.logs(stderr=True, stdout=True, stream=False,
                               timestamps=True).decode()
            )
            raise RuntimeError('Container did not stay running')
        else:
            logger.info(
                'Container logs:\n%s',
                container.logs(stderr=True, stdout=True, stream=False,
                               timestamps=True).decode()
            )
        # do the tests
        try:
            self._run_tests(container)
            db_container.stop()
            db_container.remove()
            container.stop()
            container.remove()
        except Exception as exc:
            logger.critical("Tests failed: %s", exc, exc_info=True)
            db_container.stop()
            db_container.remove()
            container.stop()
            container.remove()
            raise

    def _run_tests(self, container):
        """
        Run smoke tests against the container.

        :param container: biweeklybudget Docker container
        :type container: ``docker.models.containers.Container``
        """
        container.reload()
        cnet = container.attrs['NetworkSettings']
        c_ip = cnet['IPAddress']
        logger.debug('Container IP: %s / NetworkSettings: %s', c_ip, cnet)
        baseurl = 'http://%s' % c_ip
        failures = False
        r = requests.get('%s/' % baseurl)
        if r.status_code == 200:
            logger.info('GET /: OK (200)')
        else:
            logger.error('GET /: %s', r.status_code)
            failures = True
        exp = '<a class="navbar-brand" href="index.html">BiweeklyBudget</a>'
        if exp in r.text:
            logger.info('GET / content OK')
        else:
            logger.error('GET / content NOT OK: \n%s', r.text)
            failures = True
        r = requests.get('%s/payperiods' % baseurl)
        if r.status_code == 200:
            logger.info('GET /payperiods: OK (200)')
        else:
            logger.error('GET /payperiods: %s', r.status_code)
            failures = True
        if failures:
            raise RuntimeError('Tests FAILED.')

    def _run_mysql(self):
        """
        Run a MySQL (well, MariaDB) container to test the Docker image
        against.

        :return: MySQL container object
        :rtype: docker.models.containers.Container
        """
        img = 'mariadb:5.5.56'
        kwargs = {
            'detach': True,
            'name': 'biweeklybudget-mariadb-%s' % int(time.time()),
            'environment': {
                'MYSQL_ROOT_PASSWORD': 'root'
            }
        }
        logger.debug('Running %s with kwargs: %s', img, kwargs)
        cont = self._docker.containers.run(img, **kwargs)
        logger.debug('MySQL container running; name=%s id=%s',
                     cont.name, cont.id)
        logger.info('Sleeping 10s for stabilization...')
        time.sleep(10)
        logger.info('Creating database...')
        cmd = '/usr/bin/mysql -uroot -proot -e "CREATE DATABASE budgetfoo;"'
        logger.debug('Running: %s', cmd)
        res = cont.exec_run(cmd)
        logger.debug('Command output:\n%s', res)
        return cont

    def _build_image(self, tag):
        """
        Build Docker image, with the specified tag.

        :param tag: tag to assign to the image
        :type tag: str
        :return: tag assigned to the image
        :rtype: str
        """
        ctx = self._docker_context()
        kwargs = {
            'fileobj': ctx,
            'custom_context': True,
            'tag': '%s:%s' % (self.image_name, tag),
            'quiet': False,
            'nocache': True,
            'rm': True,
            'stream': True,
            'pull': True,
            'dockerfile': '/Dockerfile',
            'buildargs': {'version': tag},
            'decode': True
        }
        logger.info('Running docker build with args: %s', kwargs)
        res = self._docker.api.build(**kwargs)
        logger.info('Build running; output:')
        for line in res:
            try:
                print(line['stream'])
            except Exception:
                print("\t%s" % line)
        logger.info('Build complete for image: %s', tag)
        return tag

    def _check_tag(self, tag):
        """
        Confirm that the specified tag is not already present on Docker Hub or
        locally.

        :param tag: tag to check
        :type tag: str
        """
        self._check_tag_local(tag)
        logger.debug('Checking for tag on hub.docker.com')
        url = 'https://hub.docker.com/' \
              'v2/repositories/%s/tags/' % self.image_name
        res = requests.get(url)
        logger.debug('GET %s: %d', url, res.status_code)
        if res.status_code == 404:
            return
        tags = [r['name'] for r in res.json()['results']]
        logger.debug('hub.docker.com tags for %s: %s', self.image_name, tags)
        if tag in tags:
            raise RuntimeError(
                "ERROR: Tag '%s' already exists on hub.docker.com for "
                "image '%s'" % (tag, self.image_name)
            )

    def _check_tag_local(self, tag):
        """
        Confirm that the specified tag is not already present locally.

        :param tag: tag to check
        :type tag: str
        """
        expected_name = '%s:%s' % (self.image_name, tag)
        for img in self._docker.images.list():
            if expected_name in img.tags:
                raise RuntimeError(
                    'ERROR: Docker image "%s" already exists '
                    'locally' % expected_name
                )
        logger.debug('No "%s" docker image locally', expected_name)

    @property
    def _tox_dist_file(self):
        """
        Return the absolute path to the tox dist file.

        :return: path to tox dist file
        :rtype: str
        """
        fname = 'biweeklybudget-%s.zip' % VERSION
        fpath = os.path.join(self._distdir, fname)
        if not os.path.exists(fpath):
            raise RuntimeError('Does Not Exist: %s' % fpath)
        return fpath

    def _docker_context(self):
        """
        Return a BytesIO object containing a tarred Docker build context
        for the image.

        :return: Docker build context
        :rtype: io.BytesIO
        """
        logger.debug('Creating docker context (tarfile BytesIO)')
        b = BytesIO()
        tar = tarfile.open(fileobj=b, mode='w')
        self._tar_add_string_file(tar, 'Dockerfile', self._dockerfile())
        self._tar_add_string_file(tar, 'entrypoint.sh', self._entrypoint())
        tar.add(
            os.path.join(self._toxinidir, 'requirements.txt'),
            arcname='requirements.txt'
        )
        tar.add(self._tox_dist_file, arcname='biweeklybudget.zip')
        tar.add(
            os.path.join(self._toxinidir, 'dev', 'tini_0.14.0.deb'),
            arcname='tini_0.14.0.deb'
        )
        tar.close()
        b.seek(0)
        logger.debug('Docker context created')
        return b

    def _tar_add_string_file(self, tarobj, fpath, content):
        """
        Given a tarfile object, add a file to it at ``fpath``, with content
        ``content``.

        Largely based on: http://stackoverflow.com/a/40392022

        :param tarobj: the tarfile to add to
        :type tarobj: tarfile.TarFile
        :param fpath: path to put the file at in the archive
        :type fpath: str
        :param content: file content
        :type content: str
        """
        logger.debug('Adding %d-length string to tarfile at %s',
                     len(content), fpath)
        data = content.encode('utf-8')
        f = BytesIO(data)
        info = tarfile.TarInfo(name=fpath)
        info.size = len(data)
        tarobj.addfile(tarinfo=info, fileobj=f)

    def _dockerfile(self):
        """
        Return the text of a Dockerfile to build the image from.

        :return: Dockerfile text
        :rtype: str
        """
        if self.build_ver is None:
            s_copy = 'COPY biweeklybudget.zip /tmp/biweeklybudget.zip'
            s_install = '/tmp/biweeklybudget.zip'
        else:
            s_copy = ''
            s_install = 'biweeklybudget==%s' % self.build_ver
        s = DOCKERFILE_TEMPLATE.format(
            copy=s_copy,
            install=s_install
        )
        logger.debug("Dockerfile:\n%s", s)
        return s

    def _entrypoint(self):
        """
        Generate the string contents of the entrypoint script.

        :return: entrypoint script contents
        :rtype: str
        """
        s = "#!/bin/bash -ex\n"
        s += "/app/bin/python /app/bin/initdb -vv \n"
        s += "/app/bin/gunicorn -w 4 -b :80 biweeklybudget.flaskapp.app:app\n"
        logger.debug('Entrypoint script:\n%s', s)
        return s


def set_log_info():
    """set logger level to INFO"""
    set_log_level_format(logging.INFO,
                         '%(asctime)s %(levelname)s:%(name)s:%(message)s')


def set_log_debug():
    """set logger level to DEBUG, and debug-level output format"""
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level, format):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


if __name__ == "__main__":
    sys.argv.pop(0)
    set_log_debug()
    toxinidir = sys.argv[0]
    distdir = sys.argv[1]
    b = DockerImageBuilder(toxinidir, distdir)
    b.build()