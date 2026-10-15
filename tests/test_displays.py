import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_mac import displays, game_settings, wine_display
from deadlock_mac.storage import ManagerError

HOSTS = [dict(id='internal', name='Built-in', main=True, builtin=True, mirrored=False,
              quartz_bounds=[0, 0, 1512, 982], appkit_backing_scale=2, mode_pixels=[3024, 1964],
              mode_logical=[1512, 982], refresh_hz=120, session_display_id=1),
         dict(id='lg', name='LG ULTRAGEAR', main=False, builtin=False, mirrored=False,
              quartz_bounds=[1512, -458, 2560, 1440], appkit_backing_scale=1, mode_pixels=[2560, 1440],
              mode_logical=[2560, 1440], refresh_hz=144, session_display_id=3)]
OUTPUT = '''sdl index=0 instance=91 primary=1 name=Wine Monitor device=DISPLAY1 bounds=0,0,1512,982
sdl index=1 instance=92 primary=0 name=LG ULTRAGEAR device=DISPLAY2 bounds=1512,-458,2560,1440
inventory_collected=yes visual_placement_verified=no game_selection_verified=no
'''


class DisplayTests(unittest.TestCase):
    def test_explicit_secondary_and_external_never_select_main(self):
        for choice in ('lg', 'external'):
            self.assertEqual(displays.select(HOSTS, choice)['id'], 'lg')
        self.assertEqual(displays.select(HOSTS, 'default')['id'], 'internal')

    def test_disconnected_and_ambiguous_external_do_not_guess(self):
        for hosts, choice in ((HOSTS[:1], 'lg'), (HOSTS[:1], 'external'),
                              (HOSTS + [dict(HOSTS[1], id='lg2')], 'external')):
            with self.assertRaises(ManagerError):
                displays.select(hosts, choice)

    def test_mapping_uses_geometry_not_index_order_names_or_instance_ids(self):
        guest = displays.guest_displays(OUTPUT.replace('index=0', 'index=9').replace('index=1', 'index=0').replace('index=9', 'index=1'))
        self.assertEqual(displays.match_guest(HOSTS[1], guest, False)['index'], 0)
        self.assertEqual(displays.match_guest(HOSTS[1], guest, False)['bounds'][1], -458)
        with self.assertRaises(ManagerError):
            displays.match_guest(HOSTS[1], guest, True)

    def test_doubled_coordinates_are_matched_only_when_retina_is_on(self):
        guests = displays.guest_displays(OUTPUT)
        for guest in guests:
            guest['bounds'] = [v * 2 for v in guest['bounds']]
        self.assertEqual(displays.match_guest(HOSTS[1], guests, True)['index'], 1)

    def test_incomplete_duplicate_or_ambiguous_inventory_rejected(self):
        for text in (OUTPUT.replace('inventory_collected=yes', 'inventory_collected=no'),
                     OUTPUT.replace('index=1', 'index=0'), '', OUTPUT.replace('index=1', 'index=2')):
            with self.assertRaises(ManagerError):
                displays.guest_displays(text)
        guests = displays.guest_displays(OUTPUT)
        with self.assertRaises(ManagerError):
            displays.match_guest(HOSTS[1], guests + [guests[1]], False)

    def test_topology_survives_reordering_session_ids_but_not_mode_or_layout_changes(self):
        changed = copy.deepcopy(HOSTS[::-1])
        changed[0]['session_display_id'] = 99
        self.assertEqual(displays.topology(HOSTS), displays.topology(changed))
        for key, value in (('refresh_hz', 60), ('quartz_bounds', [-2560, 0, 2560, 1440]), ('main', True), ('appkit_backing_scale', 2)):
            changed = copy.deepcopy(HOSTS)
            changed[1][key] = value
            self.assertNotEqual(displays.topology(HOSTS), displays.topology(changed))


class PreparationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        prefix = self.root / 'Bottles/test'
        self.profile = dict(id='test', prefix=str(prefix), provider='wine', runtime_version='highball-wine-20261006', dxmt_version='paired')
        steam = prefix / 'drive_c/Program Files (x86)/Steam'
        steam.mkdir(parents=True); (steam / 'steam.exe').touch()
        sdl = steam / 'steamapps/common/Deadlock/game/bin/win64/SDL3.dll'
        sdl.parent.mkdir(parents=True); sdl.write_bytes(b'fixture DLL')
        video = steam / 'userdata/123/1422450/local/cfg/video.txt'
        video.parent.mkdir(parents=True)
        values = dict(game_settings.BALANCED_1080, **{'Version': '20', 'setting.monitor_index': '0', 'setting.viewportscale': '0.4'})
        video.write_text('"video.cfg"\n{\n' + ''.join(f'"{k}" "{v}"\n' for k,v in values.items()) + '}\n')
        self.video = video
        (prefix / 'user.reg').write_text('WINE REGISTRY Version 2\n\n[Software\\\\Wine\\\\Mac Driver]\n"RetinaMode"="y"\n')
        for name, value in [('host_inventory', copy.deepcopy(HOSTS)), ('probe', OUTPUT), ('wine_processes_running', False)]:
            mock = patch.object(displays, name, return_value=value).start()
            self.addCleanup(patch.stopall)
            setattr(self, name, mock)
        patch('deadlock_mac.backup.wine_processes_running', return_value=False).start()

    def prepare(self):
        return displays.prepare(self.root, self.profile, 'lg', report=lambda _: None)

    def test_prepare_secondary_preserves_quality_backs_up_and_validates(self):
        state = self.prepare()
        self.assertEqual(state['guest']['index'], 1)
        self.assertEqual(state['settings']['setting.defaultres'], '2560')
        self.assertFalse(wine_display.status(self.profile)['enabled'])
        self.assertEqual(game_settings.plan(self.profile)[2]['setting.viewportscale'], '0.4')
        self.assertTrue((Path(state['graphics_backup']) / 'video.txt').exists())
        self.assertEqual(displays.validate_launch(self.root, self.profile)['target_id'], 'lg')

    def test_live_wine_blocks_all_mutation(self):
        self.wine_processes_running.return_value = True
        before = self.video.read_bytes()
        with self.assertRaises(ManagerError): self.prepare()
        self.assertEqual(self.video.read_bytes(), before)
        self.probe.assert_not_called()
        self.assertIsNone(displays.load(self.root, self.profile))

    def test_probe_failure_rolls_back_retina_and_blocks_play(self):
        before = self.video.read_bytes()
        self.probe.side_effect = ManagerError('broken inventory')
        with self.assertRaisesRegex(ManagerError, 'broken inventory'): self.prepare()
        self.assertTrue(wine_display.status(self.profile)['enabled'])
        self.assertEqual(self.video.read_bytes(), before)
        with self.assertRaisesRegex(ManagerError, 'did not finish'):
            displays.validate_launch(self.root, self.profile)

    def test_hotplug_during_preparation_preserves_game_settings(self):
        before = self.video.read_bytes()
        self.host_inventory.side_effect = [HOSTS, HOSTS[:1]]
        with self.assertRaisesRegex(ManagerError, 'changed during'): self.prepare()
        self.assertEqual(self.video.read_bytes(), before)
        self.assertTrue(wine_display.status(self.profile)['enabled'])

    def test_changed_cloud_settings_refuse_play(self):
        self.prepare()
        self.video.write_text(self.video.read_text().replace('"setting.monitor_index" "1"', '"setting.monitor_index" "0"'))
        with self.assertRaisesRegex(ManagerError, 'Game display settings changed'):
            displays.validate_launch(self.root, self.profile)

    def test_disconnected_target_refuses_play_without_fallback_or_edits(self):
        self.prepare(); before = self.video.read_bytes()
        self.host_inventory.return_value = HOSTS[:1]
        with self.assertRaisesRegex(ManagerError, 'missing or ambiguous'):
            displays.validate_launch(self.root, self.profile)
        self.assertEqual(self.video.read_bytes(), before)

    def test_game_update_and_retina_changes_require_preparation(self):
        self.prepare()
        displays.sdl_path(self.profile).write_bytes(b'new SDL')
        with self.assertRaisesRegex(ManagerError, 'Runtime, game SDL or Retina'):
            displays.validate_launch(self.root, self.profile)

    def test_unmanaged_selection_does_not_require_helpers_or_change_files(self):
        self.prepare(); before = self.video.read_bytes()
        displays.clear(self.root, self.profile)
        self.host_inventory.side_effect = AssertionError('must not inspect hosts')
        self.assertIsNone(displays.validate_launch(self.root, self.profile))
        self.assertEqual(self.video.read_bytes(), before)

    def test_unknown_runtime_is_rejected_before_any_mutation(self):
        self.profile['runtime_version'] = 'future'
        with self.assertRaisesRegex(ManagerError, 'qualified Highball'): self.prepare()
        self.probe.assert_not_called()

class WindowEvidenceTests(unittest.TestCase):
    def test_actual_clicks_and_focus_cycle_are_distinct_from_geometry(self):
        metadata = 'test_window=1512,-458,4072,982 client=2560x1440 buffer=2560x1440\nwindow_active=1\ntest_window_closed=yes result=0\n'
        evidence = displays.window_observations(metadata, [2560, 1440])
        self.assertFalse(evidence['all_corner_targets_hit'])
        self.assertFalse(evidence['focus_left_and_returned'])
        self.assertTrue(evidence['closed_normally'])
        output = metadata + 'pointer_click=81,79\npointer_click=2482,80\npointer_click=80,1361\npointer_click=2478,1360\nwindow_active=0\nwindow_active=1\n'
        evidence = displays.window_observations(output, [2560, 1440])
        self.assertTrue(evidence['all_corner_targets_hit'])
        self.assertTrue(evidence['focus_left_and_returned'])

    def test_coordinate_offset_does_not_count_as_corner_pass(self):
        output = 'pointer_click=1592,-378\npointer_click=3992,-378\npointer_click=1592,902\npointer_click=3992,902\n'
        self.assertFalse(displays.window_observations(output, [2560, 1440])['all_corner_targets_hit'])

class LiveProbeTests(unittest.TestCase):
    def test_read_only_probe_never_shuts_down_running_steam(self):
        profile = {'prefix': '/bottle', 'runtime': '/runtime'}
        with patch.object(displays, 'wine_processes_running', return_value=True), \
             patch('deadlock_mac.game_session.processes_in_prefix', return_value={42: 'steam'}), \
             patch.object(displays, 'environment', return_value={}), \
             patch.object(displays, 'wine_binary', return_value=Path('/runtime/wine')), \
             patch.object(displays, 'helper', return_value=Path('/helper.exe')), \
             patch.object(displays, 'sdl_path', return_value=Path('/SDL3.dll')), \
             patch.object(displays.subprocess, 'run') as run:
            run.return_value.returncode = 0; run.return_value.stdout = OUTPUT
            self.assertEqual(displays.probe(profile, allow_running=True), OUTPUT)
            self.assertEqual(run.call_count, 1)
            self.assertNotIn('wineboot', run.call_args.args[0])

    def test_window_probe_refuses_an_active_session_even_with_allow_flag(self):
        with patch.object(displays, 'wine_processes_running', return_value=True), self.assertRaises(ManagerError):
            displays.probe({}, window_index=1, allow_running=True)

    def test_live_mapping_change_is_rejected_even_with_identical_host_topology(self):
        test = PreparationTests(); test.setUp()
        try:
            test.prepare()
            test.probe.return_value = OUTPUT.replace('index=0', 'index=9').replace('index=1', 'index=0').replace('index=9', 'index=1')
            with self.assertRaisesRegex(ManagerError, 'mapping changed after reconnect'):
                displays.validate_launch(test.root, test.profile)
        finally:
            test.doCleanups()
