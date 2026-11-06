import ftplib
from dataclasses import dataclass

HOSTS = ("ftp2.grandis.nu", "ftp.grandis.nu")
DEFAULT_HOST = HOSTS[0]
DEFAULT_PORT = 21
ROOT_PATH = "/Retroplay WHDLoad Packs"


@dataclass(frozen=True)
class Credentials:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool


@dataclass(frozen=True)
class RemoteNode:
    """A file or folder on the server, identified by its full remote path."""
    path: str
    is_dir: bool
    size: int

    @property
    def name(self):
        return self.path.rsplit("/", 1)[-1]


class FtpSession:
    """An FTP connection used as a context manager: it connects on entry and closes on exit."""

    def __init__(self, creds):
        self.creds = creds
        self._ftp = None

    def __enter__(self):
        c = self.creds
        ftp = ftplib.FTP_TLS() if c.use_tls else ftplib.FTP()
        try:
            ftp.connect(c.host, c.port, timeout=30)
            ftp.login(c.user, c.password)
            if c.use_tls:
                ftp.prot_p()
            ftp.encoding = "utf-8"
        except Exception:
            ftp.close()
            raise
        self._ftp = ftp
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        if self._ftp is None:
            return
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass
        self._ftp = None

    def list_dir(self, path):
        """Return the RemoteNodes directly below path."""
        try:
            nodes = []
            for name, facts in self._ftp.mlsd(path, facts=["type", "size"]):
                kind = facts.get("type", "")
                if kind in ("cdir", "pdir") or name in (".", ".."):
                    continue
                nodes.append(RemoteNode(f"{path}/{name}", kind == "dir", int(facts.get("size", 0) or 0)))
            return nodes
        except (ftplib.error_perm, AttributeError):
            pass
        # Fallback: parse Unix-style LIST output
        lines = []
        self._ftp.retrlines(f"LIST {path}", lines.append)
        nodes = []
        for line in lines:
            parts = line.split(None, 8)
            if len(parts) < 9 or parts[8] in (".", ".."):
                continue
            size = int(parts[4]) if parts[4].isdigit() else 0
            nodes.append(RemoteNode(f"{path}/{parts[8]}", line.startswith("d"), size))
        return nodes

    def retrieve(self, remote_path, callback, blocksize=64 * 1024):
        self._ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=blocksize)
