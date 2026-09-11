"""Windows Credential Manager SecretStore implementation.

This module is importable cross-platform but can only be instantiated on
Windows. It performs targeted reads/writes/deletes for an ECP-owned namespaced
identity; it never enumerates the credential store.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re

from .credentials import CredentialStateError, SecretStore


_TARGET_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


if os.name == "nt":
    class _CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


class WindowsCredentialStore(SecretStore):
    """Targeted Windows Credential Manager store; never an app-facing API."""

    _TYPE_GENERIC = 1
    _PERSIST_LOCAL_MACHINE = 2

    def __init__(self, namespace: str = "ECP") -> None:
        if os.name != "nt":
            raise OSError("Windows Credential Manager requires Windows")
        if not _TARGET_RE.fullmatch(namespace):
            raise ValueError("namespace contains invalid characters")
        self.namespace = namespace
        self._advapi = ctypes.WinDLL("advapi32", use_last_error=True)

    def target_name(self, credential_id: str, version: str) -> str:
        if not _TARGET_RE.fullmatch(credential_id) or not _TARGET_RE.fullmatch(version):
            raise ValueError("credential identity contains invalid characters")
        target = f"{self.namespace}/{credential_id}/{version}"
        if len(target) > 256:
            raise ValueError("credential target is too long")
        return target

    def _read(self, credential_id: str, version: str) -> str | None:
        target = self.target_name(credential_id, version)
        pointer = ctypes.POINTER(_CREDENTIALW)()
        ok = self._advapi.CredReadW(target, self._TYPE_GENERIC, 0, ctypes.byref(pointer))
        if not ok:
            error = ctypes.get_last_error()
            if error == 1168:  # ERROR_NOT_FOUND
                return None
            raise OSError(error, "Windows Credential Manager read failed")
        try:
            item = pointer.contents
            raw = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
            return raw.decode("utf-8")
        finally:
            self._advapi.CredFree(pointer)

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        if not isinstance(secret, str) or not secret:
            raise ValueError("secret must be a non-empty string")
        target = self.target_name(credential_id, version)
        encoded = secret.encode("utf-8")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        item = _CREDENTIALW()
        item.Type = self._TYPE_GENERIC
        item.TargetName = target
        item.CredentialBlobSize = len(encoded)
        item.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        item.Persist = self._PERSIST_LOCAL_MACHINE
        if not self._advapi.CredWriteW(ctypes.byref(item), 0):
            raise OSError(ctypes.get_last_error(), "Windows Credential Manager write failed")

    def _delete(self, credential_id: str, version: str) -> None:
        target = self.target_name(credential_id, version)
        if not self._advapi.CredDeleteW(target, self._TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error == 1168:
                return
            raise OSError(error, "Windows Credential Manager delete failed")


__all__ = ["WindowsCredentialStore"]
