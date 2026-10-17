"""Local state and verified downloads; no shell execution or credential storage."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request


class ManagerError(Exception):
    pass


def no_symlinks(path):
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ManagerError(f"Refusing a symlink in managed storage: {part}")
    return path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", value):
        raise ManagerError("Use a short profile ID containing lowercase letters, digits and hyphens.")
    return value


def private_dir(path):
    path = no_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise ManagerError(f"Not a directory: {path}")
    return path


@contextmanager
def lock(directory):
    directory = private_dir(directory)
    fd = os.open(directory / ".manager.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ManagerError("Another manager operation is running in this workspace.") from exc
        yield
    finally:
        os.close(fd)


def atomic_json(path, value):
    path = Path(path)
    private_dir(path.parent)
    if path.is_symlink():
        raise ManagerError("Refusing to replace a symlink with state.")
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, expected, destination):
    """Download only HTTPS, including redirects; fail closed on checksum mismatch."""
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ManagerError("A pinned SHA-256 is required.")
    if urllib.parse.urlparse(url).scheme != "https":
        raise ManagerError("Only HTTPS downloads are supported.")
    destination = Path(destination)
    private_dir(destination.parent)
    if destination.exists():
        if destination.is_symlink() or sha256(destination) != expected:
            raise ManagerError("Cached download failed integrity validation; preserve it for inspection.")
        return destination

    class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urllib.parse.urlparse(newurl).scheme != "https":
                raise ManagerError("Refused download redirect away from HTTPS.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    fd, partial = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
    try:
        opener = urllib.request.build_opener(HTTPSRedirect())
        request = urllib.request.Request(url, headers={"User-Agent": "deadlock-mac/0.1"})
        with os.fdopen(fd, "wb") as out, opener.open(request, timeout=45) as response:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 1024**3:
                    raise ManagerError("Download exceeded the 1 GiB limit.")
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if sha256(partial) != expected:
            raise ManagerError("Download checksum mismatch. Nothing was installed or executed.")
        os.replace(partial, destination)
    finally:
        Path(partial).unlink(missing_ok=True)
    return destination


def unpack(archive, destination, *, include=None, exclude=()):
    """Extract into a new empty directory, rejecting escaping links and special files."""
    destination = Path(destination)
    if destination.exists():
        raise ManagerError("Runtime destination already exists; installation never overwrites a runtime.")
    private_dir(destination.parent)
    with tempfile.TemporaryDirectory(prefix=".extract-", dir=destination.parent) as stage:
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            if include:
                members = [m for m in members if m.name == include or m.name.startswith(include + "/")]
                if not members:
                    raise ManagerError("Expected runtime subtree is absent from the archive.")
            members = [m for m in members if not any(m.name == e or m.name.startswith(e + "/") for e in exclude)]
            if len(members) > 20000 or sum(m.size for m in members) > 3 * 1024**3:
                raise ManagerError("Archive exceeds extraction limits.")
            for member in members:
                if Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                    raise ManagerError("Archive contains an absolute or traversing path.")
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise ManagerError("Archive contains a device, FIFO or other special file.")
                # Python's data filter rejects absolute/escaping links, path traversal
                # and dangerous permissions. Validate every member before extracting.
                tarfile.data_filter(member, stage)
            tar.extractall(stage, members=members, filter="data")
        os.rename(stage, destination)


def verify_extracted(archive, destination, *, include=None, exclude=()):
    """Compare installed bytes and links to a previously hash-verified archive."""
    destination = no_symlinks(destination)
    expected = set()
    with tarfile.open(archive) as tar:
        for member in tar:
            name = str(Path(member.name))
            if include and not (name == include or name.startswith(include + "/")):
                continue
            if any(name == e or name.startswith(e + "/") for e in exclude):
                continue
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ManagerError("Unsafe archive path during verification.")
            path = destination / name
            if member.isdir():
                continue
            expected.add(name)
            no_symlinks(path.parent)
            if member.issym():
                if not path.is_symlink() or os.readlink(path) != member.linkname:
                    raise ManagerError(f"Runtime link differs from archive: {name}")
                if not path.resolve().is_relative_to(destination.resolve()):
                    raise ManagerError(f"Runtime link escapes installation: {name}")
            elif member.isfile() or member.islnk():
                if path.is_symlink() or not path.is_file():
                    raise ManagerError(f"Runtime file is missing or replaced: {name}")
                with tar.extractfile(member) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if sha256(path) != digest:
                    raise ManagerError(f"Runtime file differs from archive: {name}")
            else:
                raise ManagerError("Unsupported archive member during verification.")
    actual = {str(p.relative_to(destination)) for p in destination.rglob("*")
              if p.is_symlink() or not p.is_dir()}
    actual.discard("manager-receipt.json")
    if actual != expected:
        raise ManagerError("Runtime contains missing or unexpected files.")
    return len(expected)
