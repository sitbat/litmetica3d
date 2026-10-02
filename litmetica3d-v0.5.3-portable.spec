# Compatibility entry point; all portable builds use the current package version.
from pathlib import Path

_spec = Path(SPECPATH) / "litmetica3d-portable.spec"
exec(compile(_spec.read_text(encoding="utf-8"), str(_spec), "exec"), globals())
