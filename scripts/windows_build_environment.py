"""Chemins DLL de compilation Windows, indépendants des outils tiers du PATH."""
from pathlib import PureWindowsPath


def windows_build_path(executable, base_prefix, system_root):
    """Limiter la résolution native à Python et Windows ; les hooks ajoutent leurs paquets."""
    python = PureWindowsPath(base_prefix)
    windows = PureWindowsPath(system_root)
    paths = (PureWindowsPath(executable).parent, python, python/'DLLs', windows/'System32', windows)
    return ';'.join(dict.fromkeys(str(path) for path in paths))
