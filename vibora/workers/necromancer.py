import os
import sys
import threading
from imp import reload
from itertools import chain
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
    """Thread that watches project files and re-run the active vibora execution."""
    def __init__(self, app, reloading: list=None, interval: float=0.5):
        """
        :: app : a valid Vibora instance
        :: reloading : list of files to keep an eye on (i.e: a config file)
        :: interval : cycle interval for file scan, default 0.1s
        """
        super().__init__()
        self.interval = interval
        self.app = app
        self.custom_files = reloading if isinstance(reloading, list) else []  # TODO: make it a list of files or folders
        self.must_work = True

    def run(self):
        mtimes = {}  # TODO: this can become quite big.. optimization?
        while self.must_work:
            # Let's not be greedy
            time.sleep(self.interval)
            # Make an iterable of tuples out of a list
            custom_files = zip(self.custom_files, (None, ))
            # Iterate over all the relevant python files and extra given files
            for filename, module in chain(self._modules(),
                                          custom_files):
                try:
                    if not filename:
                        # No file name no change
                        continue
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue
                old_time = mtimes.get(filename)
                if old_time is None:
                    # First time we see the file
                    mtimes[filename] = mtime
                    continue
                elif mtime != old_time:
                    # Notify
                    cprint('Restarting server due to changes in %s.' % filename)
                    # Clean the room
                    self.app.clean_up()
                    if module and module.__name__ != '__main__':
                        # Try to reload the module
                        reload(module)
                    # Sobstitute this execution with a new one
                    os.execv(sys.executable, ['python'] + sys.argv)

    def _modules(self):
        """This iterates over all relevant Python files.  It goes through all
        loaded files from modules, all files in folders of already loaded modules
        as well as all files reachable through a package.
        """
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
