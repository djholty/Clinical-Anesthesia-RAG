import types
import pytest


def test_startup_conversion_called(monkeypatch):
    # Create a stub module for app.extract_pdf_to_markdown
    stub = types.SimpleNamespace()
    called = {"n": 0}

    def process():
        called["n"] += 1

    stub.process_pdfs_from_folder = process
    monkeypatch.setitem(__import__("sys").modules, "app.extract_pdf_to_markdown", stub)

    import importlib
    import app.pdf_watcher as pw

    handler = pw.PdfFileHandler()
    # Directly invoke conversion method
    handler._trigger_conversion()
    assert called["n"] == 1


def test_timer_scheduled_on_event(monkeypatch, tmp_path):
    import app.pdf_watcher as pw

    # Point watch dir to tmp
    monkeypatch.setenv("PDF_WATCH_DIRECTORY", str(tmp_path))
    handler = pw.PdfFileHandler()

    scheduled = {"secs": None}

    class DummyTimer:
        def __init__(self, secs, fn):
            scheduled["secs"] = secs
        def daemon(self, *a, **k):
            pass
        def start(self):
            pass

    monkeypatch.setattr(pw.threading, "Timer", DummyTimer)

    class E:
        is_directory = False
        src_path = str(tmp_path / "x.pdf")

    handler.on_created(E())
    # default in code is 120 seconds unless overridden
    assert scheduled["secs"] in (120, int(__import__('os').getenv('PDF_QUIET_PERIOD_SECONDS', '120')))

