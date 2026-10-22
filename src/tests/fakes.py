import io

from chilichip.console import Console


class FakeConsole(Console):
    """Console that talks to BytesIO buffers instead of a serial port."""
    timeout = 5
    port = '_fakeconsole_'

    def __init__(self, reply=b''):
        self._reader = io.BytesIO(reply)
        self._writer = io.BytesIO()

    def read(self, n=1):
        return self._reader.read(n)

    def write(self, b):
        return self._writer.write(b)

    def sent(self):
        return self._writer.getvalue()

    @property
    def in_waiting(self):
        return 0

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Comport:
    def __init__(self, vid, pid, device):
        self.vid = vid
        self.pid = pid
        self.device = device
