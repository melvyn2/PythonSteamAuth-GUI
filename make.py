#!/usr/bin/env python3

#    Copyright (c) 2018 Melvyn Depeyrot
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import errno
import glob
import shutil
import subprocess
import sys
import struct
import time


if not(sys.version_info.major == 3 and sys.version_info.minor >= 6):
    raise SystemExit('ERROR: Requires python >= 3.6')


def clean():
    delete(os.path.join('build', 'PySteamAuth.build'))
    delete(os.path.join('build', 'PySteamAuth.dist'))
    delete(os.path.join('build', 'PySteamAuth.app'))
    delete('dist')
    delete('pkg')

    for f in glob.iglob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '**', '*.pyc'), recursive=True):
        delete(f)
    for root, dirnames, filenames in os.walk('.'):
        for dirname in dirnames:
            if dirname == '__pycache__':
                delete(os.path.join(root, dirname))


def delete(obj):
    try:
        if os.path.isdir(obj):
            shutil.rmtree(obj)
        else:
            os.remove(obj)
    except OSError as err:
        if err.errno != 2:
            raise err


def build_qt_files():
    psa_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PySteamAuth')
    pyuis_dir = os.path.join(psa_dir, 'PyUIs')
    uis_dir = os.path.join(psa_dir, 'UIs')
    delete(pyuis_dir)
    os.mkdir(pyuis_dir)
    built_files = []
    for f in glob.iglob(os.path.join(uis_dir, '*.ui')):
        subprocess.call([sys.executable, '-m', 'PyQt5.uic.pyuic', f, '-o',
                         os.path.join(pyuis_dir, os.path.basename(f).replace('.ui', '.py'))])
        built_files.append(os.path.basename(f).replace('.ui', ''))
    for f in glob.iglob(os.path.join(uis_dir, '*.qrc')):
        subprocess.call([sys.executable, '-m', 'PyQt5.pyrcc_main', f, '-o',
                         os.path.join(pyuis_dir, os.path.basename(f).replace('.qrc', '_rc.py'))])
        built_files.append(os.path.basename(f).replace('.qrc', '_rc'))
    with open(os.path.join(pyuis_dir, '__init__.py'), 'w') as f:
        f.write('from . import ' + ', '.join(sorted(built_files)))
    print('Built', len(built_files), 'PyUI files.')


action = sys.argv[1].lower() if len(sys.argv) >= 2 else None

if action == 'build':  # TODO add travis & appveyor CI
    if '--dont-clean' not in sys.argv:
        clean()
    if '--dont-build-qt' not in sys.argv:
        build_qt_files()
    os.chdir('build')
    try:
        pre_time = time.time()
        sp = subprocess.check_output([sys.executable, '-m', 'nuitka', '--standalone', '--follow-imports',
                       '--plugin-enable=qt-plugins=sensible,' +
                                      ('platformthemes' if sys.platform.startswith('linux') else 'styles'),
                       os.path.join('..', 'PySteamAuth', 'PySteamAuth.py')] +
                            (['--show-progress'] if '-v' in sys.argv else []))
        print('Nuitka compilation took', time.time() - pre_time, 'seconds')
    except subprocess.CalledProcessError:
        print('Nuitka compilation failed')
        sys.exit(1)

    try:
        version = subprocess.check_output(['git', 'describe', '--tags', '--exact-match'], stderr=subprocess.PIPE) \
            .decode('utf-8').strip()
    except FileNotFoundError:
        version = '0.0'
        print('Git is not installed; using default version value')
    except subprocess.CalledProcessError:
        try:
            version = 'git' + \
                      subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.PIPE) \
                          .decode('utf-8').strip()
        except subprocess.CalledProcessError:
            version = '0.0'
            print('Not a git repo; using default version value')

    if sys.platform == 'darwin':
        os.mkdir('PySteamAuth.app')
        os.mkdir(os.path.join('PySteamAuth.app', 'Contents'))
        with open('Info.template.plist') as info_f:
            info_plist = info_f.read()
        try:
            username = subprocess.check_output(['git', 'config', 'user.name'], stderr=subprocess.PIPE) \
                .decode('utf-8')\
                .replace(' ', '')\
                .replace('\n', '')
            if username == '':
                username = 'example'
        except FileNotFoundError:
            username = 'example'
            print('Git is not installed; using default package id')
        except subprocess.CalledProcessError:
            username = 'example'
            print('Could not fetch git username; using default package id')
        with open(os.path.join('PySteamAuth.app', 'Contents', 'Info.plist'), 'w') as info_f:
            info_f.write(info_plist
                         .replace('${USERNAME}', username)
                         .replace('${VERSION}', version))
        os.rename('PySteamAuth.dist', os.path.join('PySteamAuth.app', 'Contents', 'MacOS'))
        os.chdir('..')
        os.mkdir('dist')
        os.rename(os.path.join('build', 'PySteamAuth.app'), os.path.join('dist', 'PySteamAuth.app'))
    else:
        os.chdir('..')
        os.rename(os.path.join('build', 'PySteamAuth.dist'), 'dist')
    if '--zip' in sys.argv:
        try:
            os.mkdir('pkg')
        except FileExistsError:
            pass
        import platform
        archive_name = 'PySteamAuth-' + version + '-' + sys.platform + '-' + platform.machine()
        shutil.make_archive(os.path.join('pkg', archive_name), format='zip', root_dir='dist')

elif action == 'install':
    try:
        if sys.platform == 'darwin':
            if not os.path.isdir(os.path.join('bin', sys.platform, 'PySteamAuth.app')):
                print('You must build the program first, like so:\n    {0} build'.format(sys.argv[0]))
                sys.exit()

            if os.path.isdir(os.path.join(os.sep, 'Applications', 'PySteamAuth.app')):
                if '-y' in sys.argv or (input('You already have a copy of PySteamAuth installed. '
                                              'Would you like to remove it and continue? [Y/n] ').lower() in ['y', '']):
                    delete(os.path.join(os.sep, 'Applications', 'PySteamAuth.app'))
                else:
                    print('Aborted.')
                    sys.exit()
            shutil.copytree(os.path.join('bin', sys.platform, 'PySteamAuth.app'), os.path.join(os.sep, 'Applications'))
            print('PySteamAuth.app has been installed to /Applications')

        elif 'linux' in sys.platform:
            if not os.path.exists(os.path.join('dist', sys.platform, 'PySteamAuth')):
                print('You must build the program first, like so:\n    {0} build'.format(sys.argv[0]))
                sys.exit()
            if os.path.exists(os.path.join(os.sep, 'usr', 'local', 'bin', 'PySteamAuth')):
                if '-y' in sys.argv or (input('You already have a copy of PySteamAuth installed. '
                                              'Would you like to remove it and continue? [Y/n] ').lower() in ['y', '']):
                    delete(os.path.join(os.sep, 'usr', 'local', 'opt', 'PySteamAuth'))
                    delete(os.path.join(os.sep, 'usr', 'local', 'bin', 'PySteamAuth'))
                else:
                    print('Aborted.')
                    sys.exit()
            if os.path.isdir(os.path.join('dist', sys.platform, 'PySteamAuth')):
                shutil.copytree(os.path.join('dist', sys.platform, 'PySteamAuth'),
                                os.path.join(os.sep, 'usr', 'local', 'opt', 'PySteamAuth'))
                os.symlink(os.path.join(os.sep, 'usr', 'local', 'opt', 'PySteamAuth', 'PySteamAuth'),
                           os.path.join(os.sep, 'usr', 'local', 'bin', 'PySteamAuth'))
                print('PySteamAuth has been installed to /usr/local/opt/PySteamAuth and symlinked into /usr/local/bin.')
            else:
                shutil.copy2(os.path.join('dist', sys.platform, 'PySteamAuth'),
                             os.path.join(os.sep, 'usr', 'local', 'bin'))
                print('PySteamAuth has been installed to /usr/local/bin.')
            if os.path.join(os.sep, 'usr', 'local', 'bin') not in os.environ['PATH']:
                print('/usr/local/bin is not in your $PATH')
        elif sys.platform in ['windows', 'win32']:
            if not os.path.exists(os.path.join('dist', sys.platform, 'PySteamAuth')):
                print('You must build the program first, like so:\n    {0} build'.format(sys.argv[0]))
                sys.exit()
            pf = 'Program Files' + (' (x86)' if struct.calcsize('P') == 4 else '')
            if os.path.isdir(os.path.join(os.sep, pf, 'PySteamAuth')):
                if '-y' in sys.argv or\
                        (input('You already have a copy of PySteamAuth at \\{0}\\PySteamAuth. '
                               'Would you like to remove it and continue? [Y/n] '.format(pf)) in ['y', '']):
                    delete(os.path.join(os.sep, pf, 'PySteamAuth'))
                else:
                    print('Aborted.')
                    sys.exit()
            if os.path.isdir(os.path.join('dist', sys.platform, 'PySteamAuth')):
                shutil.copytree(os.path.join('dist', sys.platform, 'PySteamAuth'),
                                os.path.join(os.sep, pf, 'PySteamAuth'))
            else:
                os.mkdir(os.path.join('dist', sys.platform, 'PySteamAuth'))
                shutil.copy2(os.path.join('dist', sys.platform, 'PySteamAuth.exe'),
                             os.path.join(os.sep, pf, 'PySteamAuth'))
            os.link(os.path.join(os.sep, pf, 'PySteamAuth', 'PySteamAuth.exe'),
                    os.path.join(os.environ['userprofile'], 'Start Menu', 'Programs'))
        else:
            print('Unrecognized OS. \'{0} build <program>\' will build the executable and put it in the '
                  '\'dist\' directory.'.format(sys.argv[0]))
    except IOError as e:
        if e.errno in [errno.EACCES, errno.EPERM]:
            print('Permission denied; Try with sudo?')


elif action == 'run':
    if '--dont-rebuild-ui' not in sys.argv:
        build_qt_files()
    argv = list(filter('--dont-rebuild-ui'.__ne__, sys.argv[2:]))
    os.execl(sys.executable, sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PySteamAuth',
                                                          'PySteamAuth.py'), *argv)

elif action == 'clean':
    clean()

elif action == 'deps':
    subprocess.call([sys.executable, '-m', 'pip', 'install', '-U', '-r', 'requirements.txt'])

elif action == 'pyqt-build':
    build_qt_files()

else:
    print('Invalid option\nPossible options: build [--compact], install, run [--dont-rebuild-ui], clean, deps [-y],'
          ' pyqt-build')
