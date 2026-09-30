import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

from signalbar.settings import SettingsStore
from signalbar.update_helper import run_transaction
from signalbar.updates import (
    BETA_VERSION,
    GitHubReleaseClient,
    RELEASES_API_URL,
    UpdateError,
    UpdateManager,
    _version_order,
    _version_tuple,
    validate_and_stage_archive,
)


def write_plugin(directory: Path, version: str, marker="healthy"):
    directory.mkdir(parents=True)
    (directory / "dist").mkdir()
    (directory / "main.py").write_text(f'MARKER = "{marker}"\n', encoding="utf-8")
    (directory / "plugin.json").write_text(
        json.dumps({"name": "GabeCubeAura", "author": "Albus Querque"}), encoding="utf-8",
    )
    (directory / "package.json").write_text(
        json.dumps({"name": "gabecubeaura", "version": version}), encoding="utf-8",
    )
    (directory / "dist/index.js").write_text("export {};\n", encoding="utf-8")
    (directory / "LICENSE").write_text("fixture license\n", encoding="utf-8")
    backend = directory / "py_modules/signalbar"
    backend.mkdir(parents=True)
    (backend / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")


def write_archive(path: Path, version="1.1.0"):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "GabeCubeAura"
        write_plugin(root, version)
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for item in sorted(root.rglob("*")):
                if item.is_file():
                    archive.write(item, Path("GabeCubeAura") / item.relative_to(root))


class FakeClient:
    def __init__(self, archive: Path, version="1.1.0"):
        self.archive = archive
        self.digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.calls = []
        self.release = {
            "not_modified": False,
            "version": version,
            "tag": f"v{version}",
            "name": f"GabeCubeAura {version}",
            "notes": "Safe update",
            "html_url": f"https://github.com/Alyenax/GabeCubeAura/releases/tag/v{version}",
            "archive_name": f"GabeCubeAura-v{version}.zip",
            "archive_url": f"https://github.com/Alyenax/GabeCubeAura/releases/download/v{version}/GabeCubeAura-v{version}.zip",
            "archive_size": archive.stat().st_size,
            "archive_digest": self.digest,
            "checksums_url": f"https://github.com/Alyenax/GabeCubeAura/releases/download/v{version}/SHA256SUMS",
            "etag": '"fixture"',
        }

    def latest(self, installed_version, *, etag=""):
        self.calls.append((installed_version, etag))
        return dict(self.release)

    def read_checksum(self, release, installed_version):
        return self.digest

    def download_archive(self, release, destination, installed_version):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.archive.read_bytes())
        return self.digest


class FakeLogger:
    def warning(self, message):
        pass


class FakeResponse:
    def __init__(self, payload: bytes, headers=None):
        self.payload = payload
        self.headers = headers or {}
        self.offset = 0

    def read(self, size=-1):
        if size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeService:
    def __init__(self, fail_start=False):
        self.running = True
        self.starts = 0
        self.stops = 0
        self.fail_start = fail_start

    def stop(self):
        self.stops += 1
        self.running = False

    def start(self):
        self.starts += 1
        if self.fail_start:
            raise OSError("start failed")
        self.running = True

    def active(self):
        return self.running

    def wait_inactive(self, timeout=20):
        return not self.running


def fake_exchange(first: Path, second: Path):
    temporary = first.parent / "GabeCubeAura.exchange-test"
    first.rename(temporary)
    second.rename(first)
    temporary.rename(second)


class UpdateTests(unittest.TestCase):
    def test_versions_require_stable_semver_but_accept_local_test_install(self):
        self.assertEqual(_version_tuple("v1.1.0"), (1, 1, 0))
        self.assertEqual(_version_tuple("1.0.99-test.1", allow_test=True), (1, 0, 99, -1, 1))
        self.assertEqual(_version_tuple("1.2.0-beta.2", allow_test=True), (1, 2, 0, -2, 2))
        self.assertTrue(BETA_VERSION.fullmatch("1.2.0-beta.2"))
        self.assertLess(_version_order("1.2.0-beta.2", allow_test=True), _version_order("1.2.0"))
        for invalid in ("1.1", "1.1.0-beta", "1.2.0-beta2", "01.1.0", "latest"):
            with self.assertRaises(UpdateError, msg=invalid):
                _version_tuple(invalid)

    def test_github_client_accepts_only_expected_assets_and_prerelease_policy(self):
        digest = "a" * 64
        release = {
            "tag_name": "v1.1.0",
            "name": "GabeCubeAura 1.1.0",
            "body": "notes",
            "html_url": "https://github.com/Alyenax/GabeCubeAura/releases/tag/v1.1.0",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "GabeCubeAura-v1.1.0.zip",
                    "browser_download_url": "https://github.com/Alyenax/GabeCubeAura/releases/download/v1.1.0/GabeCubeAura-v1.1.0.zip",
                    "size": 100,
                    "digest": f"sha256:{digest}",
                },
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": "https://github.com/Alyenax/GabeCubeAura/releases/download/v1.1.0/SHA256SUMS",
                    "size": 100,
                },
            ],
        }
        def opener(request, timeout=10):
            if request.full_url.endswith("SHA256SUMS"):
                return FakeResponse(f"{digest}  GabeCubeAura-v1.1.0.zip\n".encode())
            return FakeResponse(json.dumps(release).encode(), {"ETag": '"release"'})
        client = GitHubReleaseClient(opener=opener)
        result = client.latest("1.0.0")
        self.assertEqual(result["version"], "1.1.0")
        self.assertEqual(client.read_checksum(result, "1.0.0"), digest)
        release["prerelease"] = True
        with self.assertRaises(UpdateError):
            client.latest("1.0.0")
        test_client = GitHubReleaseClient(opener=opener, allow_prerelease=True)
        with self.assertRaises(UpdateError):
            test_client.latest("1.0.99-test.1")

    def test_beta_channel_selects_latest_published_beta_or_stable_release(self):
        digest = "b" * 64

        def metadata(version, prerelease=False, draft=False):
            return {
                "tag_name": f"v{version}",
                "name": f"GabeCubeAura {version}",
                "body": "notes",
                "html_url": f"https://github.com/Alyenax/GabeCubeAura/releases/tag/v{version}",
                "draft": draft,
                "prerelease": prerelease,
                "assets": [
                    {
                        "name": f"GabeCubeAura-v{version}.zip",
                        "browser_download_url": f"https://github.com/Alyenax/GabeCubeAura/releases/download/v{version}/GabeCubeAura-v{version}.zip",
                        "size": 100,
                        "digest": f"sha256:{digest}",
                    },
                    {
                        "name": "SHA256SUMS",
                        "browser_download_url": f"https://github.com/Alyenax/GabeCubeAura/releases/download/v{version}/SHA256SUMS",
                        "size": 100,
                    },
                ],
            }

        releases = [
            metadata("1.1.1"),
            metadata("1.2.0-beta.1", prerelease=True),
            metadata("1.2.0-beta.2", prerelease=True),
            metadata("1.2.0-beta.3", prerelease=True, draft=True),
            metadata("1.3.0-beta.1", prerelease=False),
        ]

        def opener(request, timeout=10):
            self.assertEqual(request.full_url, RELEASES_API_URL)
            return FakeResponse(json.dumps(releases).encode(), {"ETag": '"beta-list"'})

        client = GitHubReleaseClient(
            opener=opener, api_url=RELEASES_API_URL, allow_prerelease=True,
        )
        result = client.latest("1.1.1")
        self.assertEqual(result["version"], "1.2.0-beta.2")
        self.assertEqual(result["etag"], '"beta-list"')

    def test_valid_archive_is_staged_and_manifest_version_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "valid.zip"
            write_archive(archive)
            root = validate_and_stage_archive(archive, base / "stage", "1.1.0")
            self.assertEqual(root.name, "GabeCubeAura")
            self.assertTrue((root / "dist/index.js").is_file())
            with self.assertRaises(UpdateError):
                validate_and_stage_archive(archive, base / "wrong", "1.2.0")

    def test_archive_rejects_traversal_symlink_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            unsafe = base / "unsafe.zip"
            with ZipFile(unsafe, "w") as archive:
                archive.writestr("GabeCubeAura/../outside", "bad")
            with self.assertRaises(UpdateError):
                validate_and_stage_archive(unsafe, base / "stage-a", "1.1.0")

            symlink = base / "symlink.zip"
            with ZipFile(symlink, "w") as archive:
                info = ZipInfo("GabeCubeAura/link")
                info.external_attr = 0o120777 << 16
                archive.writestr(info, "target")
            with self.assertRaises(UpdateError):
                validate_and_stage_archive(symlink, base / "stage-b", "1.1.0")

            duplicate = base / "duplicate.zip"
            with ZipFile(duplicate, "w") as archive:
                archive.writestr("GabeCubeAura/main.py", "one")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr("GabeCubeAura/main.py", "two")
            with self.assertRaises(UpdateError):
                validate_and_stage_archive(duplicate, base / "stage-c", "1.1.0")

    def test_stale_available_release_is_cleared_after_successful_update(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = base / "runtime/updates/update-state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({
                "phase": "available",
                "installed_version": "1.0.0",
                "available_version": "1.1.0",
                "release_notes": "old notes",
                "release_url": "https://github.com/Alyenax/GabeCubeAura/releases/tag/v1.1.0",
                "confirmation_token": "a" * 32,
                "prepared_digest": "b" * 64,
            }), encoding="utf-8")
            manager = UpdateManager(
                "1.1.0", SettingsStore(str(base / "settings.json")),
                str(base / "runtime"), str(base / "plugins/GabeCubeAura"), FakeLogger(),
            )
            status = manager.status()
            self.assertEqual(status["phase"], "up_to_date")
            self.assertEqual(status["available_version"], "")
            self.assertEqual(status["confirmation_token"], "")

    def test_manager_discovers_prepares_and_persists_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "release.zip"
            write_archive(archive)
            settings = SettingsStore(str(base / "settings/config.json"))
            manager = UpdateManager(
                "1.0.99-test.1", settings, str(base / "runtime"),
                str(base / "plugins/GabeCubeAura"), FakeLogger(), client=FakeClient(archive),
            )
            self.assertEqual(manager.check()["phase"], "available")
            prepared = manager.prepare()
            self.assertEqual(prepared["phase"], "ready")
            self.assertRegex(prepared["confirmation_token"], r"^[0-9a-f]{32}$")
            self.assertTrue((base / "runtime/updates/staged" / prepared["confirmation_token"] / "GabeCubeAura").is_dir())
            manager.set_preferences(False, False, 180, "beta")
            restored = SettingsStore(str(base / "settings/config.json")).all()
            self.assertFalse(restored["updates_auto_check"])
            self.assertFalse(restored["updates_notifications"])
            self.assertEqual(restored["updates_check_interval_minutes"], 180)
            self.assertEqual(restored["updates_channel"], "beta")

    def test_stable_110_discovers_and_prepares_stable_111(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "GabeCubeAura-v1.1.1.zip"
            write_archive(archive, "1.1.1")
            manager = UpdateManager(
                "1.1.0", SettingsStore(str(base / "settings/config.json")),
                str(base / "runtime"), str(base / "plugins/GabeCubeAura"),
                FakeLogger(), client=FakeClient(archive, "1.1.1"),
            )

            discovered = manager.check()
            prepared = manager.prepare()

            self.assertEqual(discovered["channel"], "stable")
            self.assertEqual(discovered["phase"], "available")
            self.assertEqual(discovered["available_version"], "1.1.1")
            self.assertFalse(discovered["return_to_stable"])
            self.assertEqual(prepared["phase"], "ready")
            self.assertTrue((base / "runtime/updates/staged" / prepared["confirmation_token"] / "GabeCubeAura").is_dir())

    def test_helper_launch_removes_decky_runtime_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "GabeCubeAura-v1.1.1.zip"
            write_archive(archive, "1.1.1")
            active = base / "plugins/GabeCubeAura"
            write_plugin(active, "1.1.0")
            manager = UpdateManager(
                "1.1.0", SettingsStore(str(base / "settings/config.json")),
                str(base / "runtime"), str(active), FakeLogger(),
                client=FakeClient(archive, "1.1.1"),
            )
            manager.check()
            prepared = manager.prepare()

            poisoned = {
                "PATH": "/usr/bin:/bin",
                "LD_LIBRARY_PATH": "/tmp/_MEI-decky",
                "LD_PRELOAD": "/tmp/decky-preload.so",
                "PYTHONHOME": "/tmp/decky-python",
                "PYTHONPATH": "/tmp/decky-modules",
                "LANG": "C.UTF-8",
            }
            with patch.dict("signalbar.updates.os.environ", poisoned, clear=True), \
                    patch(
                        "signalbar.updates.shutil.which",
                        side_effect=["/usr/bin/python3", "/usr/bin/systemd-run"],
                    ), \
                    patch("signalbar.updates.subprocess.run") as launched:
                accepted = manager.install(prepared["confirmation_token"])

            self.assertTrue(accepted["accepted"])
            environment = launched.call_args.kwargs["env"]
            self.assertEqual(environment["LD_LIBRARY_PATH"], "")
            self.assertNotIn("LD_PRELOAD", environment)
            self.assertNotIn("PYTHONHOME", environment)
            self.assertNotIn("PYTHONPATH", environment)
            self.assertEqual(environment["LANG"], "C.UTF-8")
            command = launched.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/systemd-run")
            self.assertEqual(command[-3], "/usr/bin/python3")

    def test_switching_from_stable_to_beta_checks_immediately_and_prepares_beta(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "beta.zip"
            write_archive(archive, "1.2.0-beta.2")
            settings = SettingsStore(str(base / "settings/config.json"))
            client = FakeClient(archive, "1.2.0-beta.2")
            manager = UpdateManager(
                "1.1.1", settings, str(base / "runtime"),
                str(base / "plugins/GabeCubeAura"), FakeLogger(), client=client,
            )

            status = manager.set_preferences(True, True, 15, "beta")

            self.assertEqual(status["channel"], "beta")
            self.assertEqual(status["phase"], "available")
            self.assertEqual(status["available_version"], "1.2.0-beta.2")
            self.assertFalse(status["return_to_stable"])
            self.assertEqual(len(client.calls), 1)
            prepared = manager.prepare()
            self.assertEqual(prepared["phase"], "ready")
            self.assertTrue((base / "runtime/updates/staged" / prepared["confirmation_token"] / "GabeCubeAura").is_dir())

    def test_switching_from_beta_to_stable_offers_verified_return_even_when_older(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "stable.zip"
            write_archive(archive, "1.1.1")
            settings = SettingsStore(str(base / "settings/config.json"))
            settings.update({"updates_channel": "beta"})
            client = FakeClient(archive, "1.1.1")
            manager = UpdateManager(
                "1.2.0-beta.2", settings, str(base / "runtime"),
                str(base / "plugins/GabeCubeAura"), FakeLogger(), client=client,
            )

            status = manager.set_preferences(True, True, 60, "stable")

            self.assertEqual(status["phase"], "available")
            self.assertEqual(status["available_version"], "1.1.1")
            self.assertTrue(status["return_to_stable"])
            prepared = manager.prepare()
            self.assertEqual(prepared["phase"], "ready")
            self.assertTrue(prepared["return_to_stable"])

    def test_new_stable_after_beta_is_a_forward_update_not_a_return(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "stable.zip"
            write_archive(archive, "1.2.0")
            settings = SettingsStore(str(base / "settings/config.json"))
            settings.update({"updates_channel": "beta"})
            manager = UpdateManager(
                "1.2.0-beta.2", settings, str(base / "runtime"),
                str(base / "plugins/GabeCubeAura"), FakeLogger(),
                client=FakeClient(archive, "1.2.0"),
            )

            status = manager.set_preferences(True, True, 1440, "stable")

            self.assertEqual(status["phase"], "available")
            self.assertEqual(status["available_version"], "1.2.0")
            self.assertFalse(status["return_to_stable"])

    def test_startup_check_runs_once_even_when_periodic_deadline_is_in_the_future(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "release.zip"
            write_archive(archive, "1.1.2")
            settings = SettingsStore(str(base / "settings/config.json"))
            client = FakeClient(archive, "1.1.2")
            manager = UpdateManager(
                "1.1.1", settings, str(base / "runtime"),
                str(base / "plugins/GabeCubeAura"), FakeLogger(), client=client,
                clock=lambda: 100,
            )
            manager._set(next_check_at=999999)

            status = manager._check_on_startup()

            self.assertEqual(status["phase"], "available")
            self.assertEqual(len(client.calls), 1)

            settings.update({"updates_auto_check": False})
            manager._check_on_startup()
            self.assertEqual(len(client.calls), 1)

    def test_health_acknowledgement_only_matches_pending_version_and_token(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime = base / "runtime"
            state = runtime / "updates/update-state.json"
            token = "a" * 32
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({
                "pending_token": token, "pending_version": "1.1.0", "phase": "restart_pending",
            }), encoding="utf-8")
            UpdateManager("1.1.0", SettingsStore(str(base / "settings.json")),
                          str(runtime), str(base / "GabeCubeAura"), FakeLogger())
            health = json.loads((runtime / f"updates/health/{token}.json").read_text(encoding="utf-8"))
            self.assertEqual(health["version"], "1.1.0")

    def test_running_backend_adopts_terminal_state_written_by_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            token = "c" * 32
            state = base / "runtime/updates/update-state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({
                "phase": "restart_pending",
                "installed_version": "1.1.0",
                "pending_token": token,
                "pending_version": "1.1.1",
            }), encoding="utf-8")
            manager = UpdateManager(
                "1.1.1", SettingsStore(str(base / "settings.json")),
                str(base / "runtime"), str(base / "plugins/GabeCubeAura"),
                FakeLogger(), clock=lambda: 100,
            )
            persisted = json.loads(state.read_text(encoding="utf-8"))
            persisted.update({
                "phase": "updated",
                "installed_version": "1.1.1",
                "pending_token": "",
                "pending_version": "",
                "completed_token": token,
                "last_result": "updated",
            })
            state.write_text(json.dumps(persisted), encoding="utf-8")

            status = manager.status()

            self.assertEqual(status["phase"], "updated")
            self.assertEqual(status["last_result"], "updated")

    def test_healthy_restart_pending_recovers_and_can_find_next_release(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            token = "d" * 32
            now = [100]
            archive = base / "GabeCubeAura-v1.1.2.zip"
            write_archive(archive, "1.1.2")
            state = base / "runtime/updates/update-state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({
                "phase": "restart_pending",
                "installed_version": "1.1.0",
                "pending_token": token,
                "pending_version": "1.1.1",
            }), encoding="utf-8")
            transaction = state.parent / f"transactions/{token}.json"
            transaction.parent.mkdir(parents=True)
            transaction.write_text(json.dumps({
                "token": token,
                "from_version": "1.1.0",
                "to_version": "1.1.1",
            }), encoding="utf-8")
            manager = UpdateManager(
                "1.1.1", SettingsStore(str(base / "settings.json")),
                str(base / "runtime"), str(base / "plugins/GabeCubeAura"),
                FakeLogger(), client=FakeClient(archive, "1.1.2"),
                clock=lambda: now[0],
            )

            now[0] = 103
            self.assertEqual(manager.status()["phase"], "restart_pending")
            now[0] = 106
            discovered = manager.check()

            self.assertEqual(discovered["phase"], "available")
            self.assertEqual(discovered["available_version"], "1.1.2")
            self.assertEqual(discovered["rollback_version"], "1.1.0")

    def test_manual_newer_install_closes_older_restart_pending_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            token = "e" * 32
            archive = base / "GabeCubeAura-v1.1.2.zip"
            write_archive(archive, "1.1.2")
            state = base / "runtime/updates/update-state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({
                "phase": "restart_pending",
                "installed_version": "1.1.0",
                "pending_token": token,
                "pending_version": "1.1.1",
            }), encoding="utf-8")
            transaction = state.parent / f"transactions/{token}.json"
            transaction.parent.mkdir(parents=True)
            transaction.write_text(json.dumps({
                "token": token,
                "from_version": "1.1.0",
                "to_version": "1.1.1",
            }), encoding="utf-8")
            manager = UpdateManager(
                "1.1.2", SettingsStore(str(base / "settings.json")),
                str(base / "runtime"), str(base / "plugins/GabeCubeAura"),
                FakeLogger(), client=FakeClient(archive, "1.1.2"),
            )

            recovered = manager.status()
            checked = manager.check()

            self.assertEqual(recovered["phase"], "updated")
            self.assertEqual(recovered["installed_version"], "1.1.2")
            self.assertEqual(checked["phase"], "up_to_date")
            self.assertEqual(checked["pending_version"], "")

    def test_update_lab_runs_all_fixed_scenarios_without_real_plugin_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "release.zip"
            write_archive(archive)
            manager = UpdateManager(
                "1.0.99-test.1", SettingsStore(str(base / "settings.json")),
                str(base / "runtime"), str(base / "real/GabeCubeAura"),
                FakeLogger(), client=FakeClient(archive),
            )
            for scenario in ("valid-package", "checksum-mismatch", "rollback"):
                result = manager.run_lab(scenario)
                self.assertTrue(result["passed"], result)
            report = json.loads(
                (base / "runtime/updates/update-lab-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual({item["scenario"] for item in report["results"]}, {
                "valid-package", "checksum-mismatch", "rollback",
            })
            self.assertFalse((base / "real/GabeCubeAura").exists())

    def _transaction(self, base: Path):
        token = "b" * 32
        active = base / "plugins/GabeCubeAura"
        staged = base / f"runtime/updates/staged/{token}/GabeCubeAura"
        write_plugin(active, "1.0.0", "old")
        write_plugin(staged, "1.1.0", "new")
        state = base / "runtime/updates/update-state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("{}", encoding="utf-8")
        return {
            "schema": 1, "token": token, "from_version": "1.0.0", "to_version": "1.1.0",
            "digest": "c" * 64, "active_dir": str(active), "staged_dir": str(staged),
            "runtime_root": str(base / "runtime/updates"), "state_path": str(state),
            "health_path": str(base / f"runtime/updates/health/{token}.json"),
            "service": "plugin_loader.service", "health_timeout": 45,
        }

    def test_transaction_swaps_only_after_stop_and_accepts_health(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw = self._transaction(base)
            settings = base / "settings/config.json"
            artwork = base / "settings/artwork-cache.json"
            settings.parent.mkdir(parents=True)
            settings.write_bytes(b'{"choice":"kept"}\n')
            artwork.write_bytes(b'{"palette":"kept"}\n')
            before = (hashlib.sha256(settings.read_bytes()).hexdigest(),
                      hashlib.sha256(artwork.read_bytes()).hexdigest())
            service = FakeService()
            result = run_transaction(raw, service=service, health_waiter=lambda *args: True,
                                     exchanger=fake_exchange)
            self.assertEqual(result, {"result": "updated", "version": "1.1.0"})
            self.assertEqual(service.stops, 1)
            self.assertEqual(service.starts, 1)
            self.assertIn('MARKER = "new"', (Path(raw["active_dir"]) / "main.py").read_text())
            rollback = base / f"runtime/updates/rollback/{raw['token']}/GabeCubeAura/main.py"
            self.assertIn('MARKER = "old"', rollback.read_text())
            after = (hashlib.sha256(settings.read_bytes()).hexdigest(),
                     hashlib.sha256(artwork.read_bytes()).hexdigest())
            self.assertEqual(after, before)
            UpdateManager(
                "1.1.0", SettingsStore(str(base / "settings/plugin.json")),
                str(base / "runtime"), str(Path(raw["active_dir"])), FakeLogger(),
            )
            self.assertFalse(rollback.parent.exists())

    def test_transaction_resumes_after_atomic_exchange_was_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw = self._transaction(base)
            active, staged = Path(raw["active_dir"]), Path(raw["staged_dir"])
            fake_exchange(active, staged)
            service = FakeService()
            result = run_transaction(raw, service=service, health_waiter=lambda *args: True,
                                     exchanger=fake_exchange)
            self.assertEqual(result["result"], "updated")
            self.assertIn('MARKER = "new"', (active / "main.py").read_text())
            rollback = base / f"runtime/updates/rollback/{raw['token']}/GabeCubeAura/main.py"
            self.assertIn('MARKER = "old"', rollback.read_text())

    def test_failed_health_check_restores_previous_plugin_without_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw = self._transaction(base)
            service = FakeService()
            result = run_transaction(raw, service=service, health_waiter=lambda *args: False,
                                     exchanger=fake_exchange)
            self.assertEqual(result["result"], "rolled_back")
            self.assertEqual(service.starts, 2)
            self.assertEqual(service.stops, 2)
            self.assertIn('MARKER = "old"', (Path(raw["active_dir"]) / "main.py").read_text())
            state = json.loads(Path(raw["state_path"]).read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "rolled_back")
            self.assertEqual(state["pending_token"], "")


if __name__ == "__main__":
    unittest.main()
