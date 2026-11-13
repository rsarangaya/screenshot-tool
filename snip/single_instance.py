"""Single-instance guard using QLocalServer/QLocalSocket."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = "SnipToolSingleInstance"


def notify_existing(name: str = NAME, timeout_ms: int = 500) -> bool:
    """True if another instance is running (it is told to show its window)."""
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(b"show")
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Listens for later launches; emits `activated` when one connects."""
    activated = Signal()

    def __init__(self, name: str = NAME, parent=None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        QLocalServer.removeServer(name)  # stale socket from a crash
        self.ok = self._server.listen(name)
        self._server.newConnection.connect(self._on_conn)

    def _on_conn(self):
        while self._server.hasPendingConnections():
            s = self._server.nextPendingConnection()
            s.disconnectFromServer()
            s.deleteLater()
            self.activated.emit()
