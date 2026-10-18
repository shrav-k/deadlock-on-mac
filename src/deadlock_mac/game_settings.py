"""Compatibility facade for profile-selected game settings adapters."""
from .games import settings_adapter
from .games.deadlock import BALANCED_1080, NATIVE_RENDERING


def plan(profile):
    return settings_adapter(profile).plan(profile)


def video_file(profile):
    return settings_adapter(profile).video_file(profile)


def rendering_snapshot(profile):
    return settings_adapter(profile).rendering_snapshot(profile)


def configure(workspace, profile, **options):
    return settings_adapter(profile).configure(workspace, profile, **options)


def configure_native(workspace, profile, **options):
    return settings_adapter(profile).configure_native(workspace, profile, **options)


def configure_fps(workspace, profile, **options):
    return settings_adapter(profile).configure_fps(workspace, profile, **options)
