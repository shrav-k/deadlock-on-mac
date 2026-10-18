"""Research adapter. Never reinterpret Deadlock settings or modify Elden Ring saves."""
from ..storage import ManagerError


def rendering_snapshot(profile):
    return {"available": False, "reason": "Elden Ring graphics settings are not yet qualified."}


def unsupported(*args, **kwargs):
    raise ManagerError("Elden Ring settings and save backup adapters are not yet qualified; no files were changed.")


plan = configure = configure_native = configure_fps = video_file = data_roots = unsupported
