import os
from collections import defaultdict
from typing import Dict, Iterable, Set, List

from .. import importcompletion

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:

    def ModuleChangedEventHandler(*args):
        return None

else:

    class ModuleChangedEventHandler(FileSystemEventHandler):  # type: ignore [no-redef]
        def __init__(self, paths: Iterable[str], on_change) -> None:
            self.dirs: Dict[str, Set[str]] = defaultdict(set)
            self.on_change = on_change
            self.modules_to_add_later: List[str] = []
            self.observer = Observer()
            self.old_dirs: Dict[str, Set[str]] = defaultdict(set)
            self.started = False
            self.activated = False
            for path in paths:
                self._add_module(path)

            super().__init__()

        def reset(self) -> None:
            self.dirs = defaultdict(set)
            del self.modules_to_add_later[:]
            self.old_dirs = defaultdict(set)
            self.observer.unschedule_all()

        def _add_module(self, path: str) -> None:
            """Add a python module to track changes"""
            path = os.path.abspath(path)
            for suff in importcompletion.SUFFIXES:
                if path.endswith(suff):
                    path = path[: -len(suff)]
                    break
            dirname = os.path.dirname(path)
            if dirname not in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
            self.dirs[dirname].add(path)

        def _add_module_later(self, path: str) -> None:
            self.modules_to_add_later.append(path)

        def track_module(self, path: str) -> None:
            """
            Begins tracking this if activated, or remembers to track later.
            """
            if self.activated:
                self._add_module(path)
            else:
                self._add_module_later(path)

        def activate(self) -> None:
            if self.activated:
                raise ValueError(f"{self!r} is already activated.")
            if not self.started:
                self.started = True
                self.observer.start()
            for dirname in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
            for module in self.modules_to_add_later:
                self._add_module(module)
            del self.modules_to_add_later[:]
            self.activated = True

        def deactivate(self) -> None:
            if not self.activated:
                raise ValueError(f"{self!r} is not activated.")
            self.observer.unschedule_all()
            self.activated = False

        def on_any_event(self, event: FileSystemEvent) -> None:
            dirpath = os.path.dirname(event.src_path)
            paths = [path + ".py" for path in self.dirs[dirpath]]
            if event.src_path in paths:
                self.on_change(files_modified=[event.src_path])
