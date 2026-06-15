"""Standalone regression check for Recorder.sck_failure_reason.

Run with:  uv run python tests/test_recorder_warning.py

The project has no test framework, so this is a dependency-free script. It
verifies that a meeting which cannot capture remote-participant audio is
reported via ``sck_failure_reason`` instead of silently degrading to
mic-only (the bug that hid a revoked Screen Recording permission for weeks).
"""
from pathlib import Path

from trnscrb import recorder as rec


class _FakeStream:
    """Stand-in for sounddevice.InputStream so no real mic is opened."""
    def __init__(self, *args, **kwargs): pass
    def start(self): pass
    def stop(self): pass
    def close(self): pass


class _FakeSCK:
    def __init__(self, bundle_id): self.bundle_id = bundle_id
    def start(self): pass
    def stop(self): return None


class _RaisingSCK:
    def __init__(self, bundle_id): pass
    def start(self): raise RuntimeError("boom")


def _recorder(*, bundle_id, has_binary, has_permission, sck=_FakeSCK):
    rec.sd.InputStream = _FakeStream  # never touch the real microphone
    rec.find_binary = lambda: Path("/fake/sck-capture") if has_binary else None
    rec.check_permission = lambda: has_permission
    rec.SCKCapture = sck
    r = rec.Recorder(app_bundle_id=bundle_id)
    r.start()
    return r


def main() -> None:
    # mic-only mode (no meeting app detected) must never warn
    r = _recorder(bundle_id=None, has_binary=True, has_permission=True)
    assert r.sck_failure_reason is None, r.sck_failure_reason
    r.stop()

    # working meeting capture must not warn, and must hold an SCK handle
    r = _recorder(bundle_id="us.zoom.xos", has_binary=True, has_permission=True)
    assert r.sck_failure_reason is None, r.sck_failure_reason
    assert r._sck is not None
    r.stop()

    # permission denied -> warn, naming Screen Recording
    r = _recorder(bundle_id="us.zoom.xos", has_binary=True, has_permission=False)
    assert r.sck_failure_reason and "Screen Recording" in r.sck_failure_reason
    r.stop()

    # helper binary missing -> warn, pointing at the installer
    r = _recorder(bundle_id="us.zoom.xos", has_binary=False, has_permission=True)
    assert r.sck_failure_reason and "install" in r.sck_failure_reason.lower()
    r.stop()

    # SCK raises while starting -> warn, and no SCK handle is kept
    r = _recorder(bundle_id="us.zoom.xos", has_binary=True, has_permission=True,
                  sck=_RaisingSCK)
    assert r.sck_failure_reason is not None
    assert r._sck is None
    r.stop()

    print("All Recorder.sck_failure_reason checks passed.")


if __name__ == "__main__":
    main()
