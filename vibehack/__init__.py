import importlib.metadata

try:
    __version__ = importlib.metadata.version("vibehack")
except importlib.metadata.PackageNotFoundError:
    # Fallback for development/uninstalled mode
    __version__ = "2.7.0"
