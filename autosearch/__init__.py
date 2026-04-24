from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("autosearch")
except PackageNotFoundError:
    __version__ = "dev"
