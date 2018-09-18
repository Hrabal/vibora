import os
import sys
import threading
from imp import reload_module
from itertools import zip_longest
import time
from typing import Callable
from ..utils import cprint


class Necromancer(threading.Thread):

    def __init__(self, app, spawn_function: Callable, interval: int=5):
        super().__init__()
        self.app = app
        self.spawn_function = spawn_function
        self.interval = interval
        self.must_work = True

    def run(self):
        while self.must_work:
            time.sleep(self.interval)
            workers_alive = []
            for worker in self.app.workers:
                if not worker.is_alive():
                    worker = self.spawn_function()
                    worker.start()
                    workers_alive.append(worker)
                else:
                    workers_alive.append(worker)
            self.app.workers = workers_alive


class Guardian(threading.Thread):
    def __init__(self, app, init_args: tuple, custom_files: list=None, interval: int=1):
        self.interval = interval
        self.custom_files = custom_files or []

    def run(self):
        mtimes = {}
        while 1:
            time.sleep(self.interval)
            for filename, module in chain(self._modules(),
                                          zip_longest(self.custom_files,
                                                      (None, ))):
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue

                old_time = mtimes.get(filename)
                if old_time is None:
                    mtimes[filename] = mtime
                    continue
                elif mtime > old_time:
                    cprint('Restarting server due to changes in %s.' % filename)
                    if  module:
                        reload_module(module)
                    # Tear down everything...
                    self.app.clean_up()
                    # ..and recreate.
                    self.app = self.app.__class__(*init_args)

    def _iter_module_files(self):
        """This iterates over all relevant Python files.  It goes through all
        loaded files from modules, all files in folders of already loaded modules
        as well as all files reachable through a package.
        """
        # The list call is necessary on Python 3 in case the module
        # dictionary modifies during iteration.
        for module in list(sys.modules.values()):
            if module is None:
                continue
            filename = getattr(module, '__file__', None)
            if filename:
                if os.path.isdir(filename) and \
                   os.path.exists(os.path.join(filename, "__init__.py")):
                    filename = os.path.join(filename, "__init__.py")

                old = None
                while not os.path.isfile(filename):
                    old = filename
                    filename = os.path.dirname(filename)
                    if filename == old:
                        break
                else:
                    if filename[-4:] in ('.pyc', '.pyo'):
                        filename = filename[:-1]
                    yield filename, module
