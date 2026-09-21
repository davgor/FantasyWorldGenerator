"""Every subprocess the suite chain spawns is bounded, and the runner names its child.

Stopping a run used to kill the wrapper and leave the work running: `--stage repo-tests`
is three processes deep -- `tools/validate_repo.py` spawns `unittest discover -s tests`,
inside which `tests/test_showcase.py` spawns the showcase exporter -- and killing the
outermost PID left two live descendants, each holding a world in memory. See
`board/done/PERF-SUITE-RUNNER-ORPHANS-CHILD.md`.

Three assertions, none of which needs to kill anything it did not start:

1. A census, by walking the AST rather than grepping. A grep over these directories
   counts comments and strings and will not reproduce the same number. Every spawn site
   under `tools/`, and in `tests/test_showcase.py`, either passes a `timeout=` or
   terminates its child in a `finally` in the same function.
2. The suite runner prints the PID it got back, so a survivor found alive an hour later
   can be matched to the run that started it. Killing by executable name is not a
   workaround on a shared tree: the process list is full of other sessions' work.
3. The suite runner reaps the whole tree, not just the handle it holds. Every process in
   this probe is one the test started itself, so the hazard the card describes -- killing
   a peer's run -- is not in play, and nothing is ever matched by image name.

   Two facts about this machine make the obvious version of that assertion worthless, and
   both were measured on 2026-09-21 rather than reasoned:

   * CPython's `subprocess.run` ALREADY kills its direct child under a bare `except:`, so
     "the child is dead" passes against the unfixed tree and proves nothing.
   * `sys.executable` is a ~5 MB `Scripts/python.exe` shim. `Popen` hands back the shim's
     PID and the work runs in a different process, so `poll()` on the handle answers a
     question about the launcher rather than about the worker.

   So the assertion that carries weight is about the GRANDCHILD -- the level that in a
   real run is the showcase exporter holding gigabytes -- and liveness is read from a
   socket the process itself holds rather than from a PID or a handle.

The raw site count is deliberately NOT pinned to an integer. What must not grow is the
number of UNPROTECTED sites, and that is pinned at zero; pinning the total as well would
turn any unrelated tool gaining a `git rev-parse` into a red suite, which is a test that
fails for a reason nobody can act on.
"""

import ast
import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The five names that start a process. `subprocess.run` and `check_output` wait; `Popen`
# does not, which is why holding the handle is what makes cleanup possible at all.
SPAWNS = ("run", "Popen", "check_output", "check_call", "call")

# The suite chain the card is about: the parent of every local and CI suite run, plus the
# one test module that spawns a world generator from inside a discovered test.
SCOPE = ("tools", "tests/test_showcase.py")


def _load_validate_repo():
    """Import `tools/validate_repo.py` by path; it is a script, not a package module."""
    spec = importlib.util.spec_from_file_location(
        "fwg_validate_repo_under_test", ROOT / "tools" / "validate_repo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scoped_modules():
    for entry in SCOPE:
        path = ROOT / entry
        if path.is_file():
            yield path
            continue
        for candidate in sorted(path.rglob("*.py")):
            if "__pycache__" not in candidate.parts:
                yield candidate


def _reapers(tree):
    """Names of functions in this module that stop a process.

    Either directly -- `x.terminate()` / `x.kill()` -- or by handing the PID to
    `taskkill` / `kill`, which is what walking a process tree needs and what a plain
    `terminate()` cannot do.
    """
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if (isinstance(call.func, ast.Attribute)
                    and call.func.attr in ("terminate", "kill")):
                names.add(node.name)
            for argument in ast.walk(call):
                if (isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)
                        and argument.value in ("taskkill", "kill")):
                    names.add(node.name)
    return names


def _terminating_functions(tree):
    """Function nodes holding a `finally` that stops the child, directly or by delegation.

    Scoped to the enclosing function rather than the whole module on purpose: a module
    that cleans up one child says nothing about a second spawn site elsewhere in it.

    Delegation has to count, or this check punishes the better shape. `validate_repo.run`
    ends `finally: reap(process)`, and `reap` is where terminate, the bounded wait, the
    escalation and the tree walk live. An earlier version of this predicate looked only
    for a literal `.terminate()` inside the `finally` and reported that exact refactor as
    a regression -- a near-miss match answering a different question.
    """
    helpers = _reapers(tree)
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Try) or not inner.finalbody:
                continue
            for statement in inner.finalbody:
                for call in ast.walk(statement):
                    if not isinstance(call, ast.Call):
                        continue
                    if (isinstance(call.func, ast.Attribute)
                            and call.func.attr in ("terminate", "kill")):
                        out.add(node)
                    elif isinstance(call.func, ast.Name) and call.func.id in helpers:
                        out.add(node)
    return out


def census():
    """(rows, files) where a row is (relative path, line, call, bounded, cleaned)."""
    rows, files = [], set()
    for path in _scoped_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        cleaners = _terminating_functions(tree)
        # Map each statement back to the function that holds it. Walking parents is not
        # available on an ast node, so the containing function is resolved by descent.
        holder = {}
        for function in cleaners:
            for inner in ast.walk(function):
                holder[id(inner)] = function
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in SPAWNS:
                continue
            base = node.func.value
            if not (isinstance(base, ast.Name) and base.id == "subprocess"):
                continue
            found = True
            rows.append((path.relative_to(ROOT).as_posix(), node.lineno, node.func.attr,
                         any(k.arg == "timeout" for k in node.keywords),
                         id(node) in holder))
        if found:
            files.add(path)
    return rows, files


class SubprocessCensusTests(unittest.TestCase):
    def test_every_spawn_in_the_suite_chain_is_bounded(self):
        rows, files = census()
        self.assertTrue(rows, "the AST census found no spawn sites at all, which means it "
                              "stopped matching rather than that the sites went away")
        unprotected = ["%s:%d subprocess.%s" % (r[0], r[1], r[2])
                       for r in rows if not r[3] and not r[4]]
        cleaners = sorted({r[0] for r in rows if r[4]})
        self.assertEqual(
            unprotected, [],
            "%d spawn site(s) of %d across %d file(s) neither pass a timeout= nor "
            "terminate their child in a finally, so an interrupted parent leaves them "
            "running: %s. Files that do clean up: %s"
            % (len(unprotected), len(rows), len(files), ", ".join(unprotected),
               ", ".join(cleaners) or "none"))

    def test_suite_runner_names_the_child_pid(self):
        module = _load_validate_repo()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            module.run(sys.executable, "-c", "pass")
        printed = buffer.getvalue()
        self.assertIn("pid", printed.lower(),
                      "the suite runner printed %r, which names no PID, so a python "
                      "process found alive an hour later cannot be matched to the run "
                      "that started it" % printed.strip())
        digits = [word.strip("[]()") for word in printed.replace("pid", " ").split()]
        self.assertTrue(any(word.isdigit() for word in digits),
                        "the suite runner's output says 'pid' but carries no number: %r"
                        % printed.strip())

    @unittest.skipUnless(os.name == "nt", "tree termination is implemented for Windows "
                                          "only; the POSIX grandchild case is open and is "
                                          "recorded as open in the card")
    def test_suite_runner_reaps_the_whole_tree_and_not_just_its_handle(self):
        """The GRANDCHILD must be dead too, which is the process actually holding a world.

        This mirrors `--stage repo-tests`: the runner spawns a middle process which spawns
        a leaf, the same shape as `validate_repo` -> `unittest discover` ->
        `tests/test_showcase.py`'s exporter. Terminating the handle alone kills the middle
        and leaves the leaf running -- measured twice on 2026-09-21 -- because the middle
        is hard-killed and never runs its own cleanup.

        Liveness is read from a socket, not a PID. Each level dials back here and then
        sleeps; if the process dies the OS drops its end and `recv` returns immediately,
        with a reset rather than a clean close when it was force-killed. That matters on
        this machine because `sys.executable` is a shim: `Popen` hands back a ~5 MB
        launcher and the work happens in a different PID, so a check on the handle's
        `poll()` answers a question about the launcher. The socket reports on whichever
        process is really holding it.
        """
        module = _load_validate_repo()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        port = listener.getsockname()[1]

        with tempfile.TemporaryDirectory() as temporary:
            leaf = Path(temporary) / "leaf.py"
            middle = Path(temporary) / "middle.py"
            # No %-formatting in these sources: the probe reports its own PID, and a
            # literal %d here would be consumed by the formatting that builds the file.
            dial = ("import os, socket, sys, time\n"
                    "s = socket.create_connection(('127.0.0.1', int(sys.argv[1])))\n"
                    "s.sendall(str(os.getpid()).encode() + b'|{tag}')\n")
            leaf.write_text(dial.format(tag="leaf") + "time.sleep(120)\n",
                            encoding="utf-8")
            middle.write_text(
                "import subprocess\n"
                + dial.format(tag="middle")
                + "subprocess.Popen([sys.executable, %r, sys.argv[1]])\n" % str(leaf)
                + "time.sleep(120)\n", encoding="utf-8")

            dialled, ready = {}, threading.Event()

            def accept_both():
                listener.settimeout(40)
                try:
                    for _ in range(2):
                        conn, _ = listener.accept()
                        pid, tag = conn.recv(64).decode().split("|")
                        dialled[tag] = (conn, int(pid))
                finally:
                    ready.set()

            accepting = threading.Thread(target=accept_both, daemon=True)
            accepting.start()

            real_popen = subprocess.Popen
            interrupted = []

            class InterruptingPopen(real_popen):
                def wait(self, timeout=None):
                    # Interrupt only once the whole tree exists, or this would be
                    # measuring a race instead of the cleanup.
                    if not interrupted:
                        interrupted.append(self)
                        ready.wait(timeout=45)
                        raise KeyboardInterrupt("simulated Ctrl-C while the tree runs")
                    return super().wait(timeout=timeout)

            module.subprocess.Popen = InterruptingPopen
            try:
                with self.assertRaises(KeyboardInterrupt), redirect_stdout(io.StringIO()):
                    module.run(sys.executable, str(middle), str(port))
                accepting.join(timeout=5)
                self.assertEqual(sorted(dialled), ["leaf", "middle"],
                                 "the probe tree never fully started, so this test "
                                 "measured nothing: %s" % sorted(dialled))
                verdict = {tag: self._is_dead(conn) for tag, (conn, _) in dialled.items()}
            finally:
                module.subprocess.Popen = real_popen
                self._cleanup(dialled)

        self.assertTrue(verdict["middle"],
                        "the middle process survived the interrupt; the runner did not "
                        "even reap the child it holds a handle to")
        self.assertTrue(
            verdict["leaf"],
            "the GRANDCHILD (pid %d) was still running after the suite runner was "
            "interrupted. This is the orphan: in a real run it is the showcase exporter "
            "holding gigabytes, and it is anonymous, so nobody can safely kill it on a "
            "machine five sessions share." % dialled["leaf"][1])

    @staticmethod
    def _is_dead(conn):
        conn.settimeout(6)
        try:
            # b'' is a clean close; a reset is what a force-kill produces. Either way the
            # process holding this socket is gone.
            return conn.recv(16) == b""
        except ConnectionResetError:
            return True
        except socket.timeout:
            return False

    def _cleanup(self, dialled):
        """Kill only the PIDs this test created, by PID, never by image name."""
        for _tag, (conn, pid) in dialled.items():
            if self._is_dead(conn):
                continue
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)]
                           if os.name == "nt" else ["kill", "-9", str(pid)],
                           capture_output=True, timeout=60)


if __name__ == "__main__":
    unittest.main()
