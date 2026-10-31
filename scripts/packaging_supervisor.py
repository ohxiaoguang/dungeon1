#!/usr/bin/env python3
"""Own one command group, reap its leader and stop remaining group members.

The Swift executor remains the task manager. This small POSIX shim provides the
new session that Foundation Process does not portably expose. No shell is used.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('missing executable')
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)

    def event(**values):
        print('@@NX_EXEC:' + args.token + '@@' + json.dumps(values), file=sys.stderr, flush=True)

    parent = os.getppid()
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        # Do not serialize argv or the inherited environment.
        event(event='launch-error', message=str(exc))
        return 127
    group = child.pid
    event(event='ready', pgid=group)

    def send(sig):
        try:
            os.killpg(group, sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            event(event='cleanup-error', message='Cannot signal task process group')
            return False

    stop_at = None
    while child.poll() is None:
        if stopped or os.getppid() != parent:
            if stop_at is None:
                stop_at = time.monotonic()
                send(signal.SIGTERM)
            elif time.monotonic() - stop_at > 0.5:
                send(signal.SIGKILL)
        time.sleep(0.04)
    code = child.wait()
    # A shell/driver can exit before children which still hold output pipes.
    # Never let those descendants outlive a completed task unnoticed.
    remaining = send(signal.SIGTERM)
    if remaining:
        time.sleep(0.2)
        send(signal.SIGKILL)
    event(event='exit', code=code, descendant_cleanup_attempted=remaining)
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    sys.exit(main())
