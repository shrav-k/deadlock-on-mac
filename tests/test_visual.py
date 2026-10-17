import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from deadlock_mac import visual
from deadlock_mac.storage import ManagerError, atomic_json


class VisualTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.profile = {"id": "test", "provider": "wine", "prefix": str(self.root / "Bottles/test")}
        self.calls = []
        self.window = {"window_id": 10, "pid": 123, "title": "Game", "on_screen": True,
                       "bounds": [1512, -458, 2560, 1440]}
        for name, value in (("candidates", {"123": "identity"}), ("game_mode.process_identity", "identity")):
            mock = patch("deadlock_mac.visual." + name, return_value=value)
            mock.start(); self.addCleanup(mock.stop)

    def backend(self, workspace, request):
        self.calls.append(request)
        if request["command"] == "windows": return {"windows": [copy.deepcopy(self.window)]}
        if request["command"] == "capture":
            Path(request["output"]).write_bytes(b"test PNG")
            return {**self.window, "pixels": [2560, 1440], "output": request["output"]}
        return {"events_posted": 2, "verified_effect": False}

    def capture(self):
        return visual.capture(self.root, self.profile, "deadlock", backend=self.backend)

    def test_capture_private_receipt_and_largest_window(self):
        state = self.capture()
        self.assertEqual(Path(state["output"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual(state["bounds"], [1512, -458, 2560, 1440])
        self.assertEqual(state["process_identity"], "identity")
        self.assertFalse(state["input_used"])
        self.assertEqual(self.calls[1]["candidates"], {"123": "identity"})

    def test_disabled_session_never_sends_input(self):
        state = self.capture(); before = len(self.calls)
        with self.assertRaisesRegex(ManagerError, "Enable"):
            visual.act(self.root, self.profile, state["id"], "key", key="escape", backend=self.backend)
        self.assertEqual(len(self.calls), before)

    def test_another_space_is_capturable_but_visible_window_is_preferred(self):
        self.window["on_screen"] = False
        self.assertFalse(self.capture()["on_screen"])
        def backend(workspace, request):
            if request["command"] == "windows":
                return {"windows": [dict(self.window, window_id=20, bounds=[0,0,4000,3000]),
                                    dict(self.window, on_screen=True)]}
            return self.backend(workspace, request)
        state = visual.capture(self.root, self.profile, "steam", backend=backend)
        self.assertEqual(state["window_id"], 10)

    def test_click_is_consumed_and_followed_by_new_image(self):
        state = self.capture(); visual.session(self.root, self.profile, True)
        after = visual.act(self.root, self.profile, state["id"], "click", 1280, 720, backend=self.backend)
        self.assertNotEqual(after["capture"]["id"], state["id"])
        click = next(c for c in self.calls if c["command"] == "click")
        self.assertEqual(click["pixels"], [2560, 1440])
        self.assertEqual(click["bounds"], [1512, -458, 2560, 1440])
        self.assertFalse(after["action"]["effect_verified"])
        with self.assertRaisesRegex(ManagerError, "already used"):
            visual.act(self.root, self.profile, state["id"], "click", 1280, 720, backend=self.backend)

    def test_revoked_and_expired_input_sessions_fail(self):
        visual.session(self.root, self.profile, True)
        self.assertTrue(visual.session(self.root, self.profile)["active"])
        visual.session(self.root, self.profile, False)
        self.assertFalse(visual.session(self.root, self.profile)["active"])
        path = visual.folder(self.root, self.profile) / "input-session.json"
        atomic_json(path, {"enabled": True, "expires_at": time.time()-1})
        self.assertFalse(visual.session(self.root, self.profile)["active"])

    def test_stale_future_wrong_profile_prefix_and_used_captures_fail(self):
        state = self.capture(); now = state["created_at"]
        for change in ({"created_at": now-61}, {"created_at": now+1}, {"input_used": True},
                       {"profile": "other"}, {"prefix": "/other"}, {"target": "finder"}, {"schema": 5}):
            with self.subTest(change=change), self.assertRaises(ManagerError):
                visual.validate_input({**state, **change}, self.profile, "key", key="escape", now=now)

    def test_bad_coordinates_keys_and_nonfinite_numbers_fail(self):
        state = self.capture()
        for x,y in [(-1,0),(2560,0),(0,1440),(float('nan'),0),(float('inf'),0),(True,0),(None,0)]:
            with self.subTest(x=x,y=y), self.assertRaises(ManagerError):
                visual.validate_input(state,self.profile,"click",x,y)
        for key in [None,"command+q","password","shift+tab"]:
            with self.subTest(key=key), self.assertRaises(ManagerError):
                visual.validate_input(state,self.profile,"key",key=key)

    def test_pid_reuse_and_image_tampering_fail_before_input(self):
        state = self.capture(); visual.session(self.root,self.profile,True)
        with patch.object(visual,'candidates',return_value={"123":"reused"}), self.assertRaisesRegex(ManagerError,"reused"):
            visual.act(self.root,self.profile,state['id'],'key',key='escape',backend=self.backend)
        Path(state['output']).write_bytes(b'changed')
        with self.assertRaisesRegex(ManagerError,'image changed'):
            visual.act(self.root,self.profile,state['id'],'key',key='escape',backend=self.backend)
        self.assertFalse(any(c['command']=='key' for c in self.calls))

    def test_movement_hold_is_bounded_and_recorded(self):
        state = self.capture(); visual.session(self.root, self.profile, True)
        for command, key, duration in [("key", "escape", 500), ("key", "q", 500),
                                       ("click", None, 500), ("key", "w", 1001),
                                       ("key", "w", 0), ("key", "w", True),
                                       ("key", "w", 100.5)]:
            with self.subTest(command=command, key=key, duration=duration), self.assertRaises(ManagerError):
                visual.validate_input(state, self.profile, command, 10, 10, key, hold_ms=duration)
        result = visual.act(self.root, self.profile, state['id'], 'key', key='w',
                            hold_ms=1000, backend=self.backend)
        self.assertEqual(result['action']['hold_ms'], 1000)
        self.assertEqual(next(c for c in self.calls if c['command']=='key')['hold_ms'], 1000)

    def test_capture_and_input_verify_only_the_selected_window_owner(self):
        # Steam's background renderer can exit while the main UI remains alive.
        with patch.object(visual, 'candidates', return_value={'123': 'identity', '456': 'transient renderer'}):
            state = self.capture(); visual.session(self.root, self.profile, True)
            visual.act(self.root, self.profile, state['id'], 'key', key='escape', backend=self.backend)
        for call in self.calls:
            if call['command'] in ('capture', 'key'):
                self.assertEqual(call['candidates'], {'123': 'identity'})

    def test_unknown_input_result_consumes_capture_and_records_failure(self):
        state = self.capture(); visual.session(self.root,self.profile,True)
        def broken(w,r):
            if r['command']=='key': raise ManagerError('timed out')
            return self.backend(w,r)
        with self.assertRaisesRegex(ManagerError,'timed out'):
            visual.act(self.root,self.profile,state['id'],'key',key='escape',backend=broken)
        path=visual.folder(self.root,self.profile)/(state['id']+'.json')
        self.assertTrue(json.loads(path.read_text())['input_used'])

    def test_unrelated_window_and_pid_change_cannot_create_input_receipt(self):
        self.window['pid']=999
        with self.assertRaisesRegex(ManagerError,'unrelated'): self.capture()
        self.window['pid']=123
        with patch.object(visual.game_mode,'process_identity',return_value='new'),self.assertRaisesRegex(ManagerError,'changed'):
            self.capture()
        self.assertFalse(list(visual.folder(self.root,self.profile).glob('*.png')))

    def test_storage_limit_and_linked_receipt_fail_closed(self):
        state=self.capture()
        with patch.object(visual,'MAX_STORAGE',1),self.assertRaisesRegex(ManagerError,'limit'): self.capture()
        root=visual.folder(self.root,self.profile)
        (root/'linked.json').symlink_to(root/(state['id']+'.json'))
        with self.assertRaisesRegex(ManagerError,'symlink'):
            visual.act(self.root,self.profile,'linked','key',key='escape',backend=self.backend)

    def test_missing_window_fails_without_capturing_desktop(self):
        with self.assertRaisesRegex(ManagerError,'No visible'):
            visual.capture(self.root,self.profile,'deadlock',99,backend=self.backend)
        self.assertEqual([x['command'] for x in self.calls],['windows'])
