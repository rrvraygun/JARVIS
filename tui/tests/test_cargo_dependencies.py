from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui import cargo_download, cargo_vendor
from jarvis_tui.operation_workflow import OperationWorkflow
from jarvis_tui.outcome_verification import verify


def crate_bytes(member="fixture_dep-0.1.0/src/lib.rs", *, symlink=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in [
            (
                "fixture_dep-0.1.0/Cargo.toml",
                b'[package]\nname="fixture_dep"\nversion="0.1.0"\nedition="2021"\n',
            ),
            (member, b"pub fn value() -> u32 { 7 }\n"),
        ]:
            item = tarfile.TarInfo(name)
            item.size = len(data)
            if symlink and name == member:
                item.type = tarfile.SYMTYPE
                item.linkname = "/etc/passwd"
            archive.addfile(item, io.BytesIO(data))
    return buffer.getvalue()


class CargoDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_download_requests_one_exact_url_and_checks_hash(self):
        data = b"fixture archive"
        checksum = hashlib.sha256(data).hexdigest()
        response = Mock(status=200)
        response.getheader.side_effect = lambda name, default=None: default
        response.read.side_effect = [data, b""]
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(cargo_download.http.client, "HTTPSConnection", return_value=connection):
            result = cargo_download.download(
                "fixture_dep", "0.1.0", checksum, self.root / "package.crate"
            )
        self.assertEqual(result["status"], "downloaded")
        connection.request.assert_called_once()
        self.assertEqual(
            connection.request.call_args.args[:2],
            ("GET", "/crates/fixture_dep/fixture_dep-0.1.0.crate"),
        )

    def test_redirect_is_not_followed_and_partial_file_is_retained(self):
        connection = Mock()
        connection.getresponse.return_value = Mock(status=302)
        target = self.root / "partial.crate"
        with (
            patch.object(cargo_download.http.client, "HTTPSConnection", return_value=connection),
            self.assertRaises(ValueError),
        ):
            cargo_download.download("fixture_dep", "0.1.0", "a" * 64, target)
        connection.request.assert_called_once()
        self.assertTrue(target.exists())

    def test_checksum_partial_and_size_failures_never_retry(self):
        for index, failure in enumerate(("checksum", "partial", "size")):
            response = Mock(status=200)
            response.getheader.side_effect = lambda name, default=None: (
                str(cargo_download.MAX_ARCHIVE + 1)
                if name == "Content-Length" and failure == "size"
                else default
            )
            response.read.side_effect = (
                [b"fixture", OSError("disconnected")] if failure == "partial" else [b"fixture", b""]
            )
            connection = Mock()
            connection.getresponse.return_value = response
            with (
                self.subTest(failure=failure),
                patch.object(
                    cargo_download.http.client, "HTTPSConnection", return_value=connection
                ),
                self.assertRaises((OSError, ValueError)),
            ):
                cargo_download.download(
                    "fixture_dep", "0.1.0", "a" * 64, self.root / f"partial-{index}.crate"
                )
            connection.request.assert_called_once()
            self.assertTrue((self.root / f"partial-{index}.crate").exists())

    def test_vendor_rejects_duplicates_and_excessive_expansion(self):
        for index, data in enumerate((crate_bytes("fixture_dep-0.1.0/Cargo.toml"), crate_bytes())):
            (self.root / "fixture_dep-0.1.0.crate").write_bytes(data)
            metadata = [
                {
                    "name": "fixture_dep",
                    "version": "0.1.0",
                    "checksum": hashlib.sha256(data).hexdigest(),
                }
            ]
            with (
                patch.object(cargo_vendor, "MAX_EXPANDED", 128 * 1024 * 1024 if index == 0 else 5),
                self.assertRaises((OSError, ValueError)),
            ):
                cargo_vendor.unpack(metadata, self.root / f"reject-{index}", archive_root=self.root)

    def test_vendor_rejects_traversal_and_links(self):
        for index, (member, link) in enumerate(
            [("../escaped", False), ("fixture_dep-0.1.0/link", True)]
        ):
            data = crate_bytes(member, symlink=link)
            (self.root / "fixture_dep-0.1.0.crate").write_bytes(data)
            metadata = [
                {
                    "name": "fixture_dep",
                    "version": "0.1.0",
                    "checksum": hashlib.sha256(data).hexdigest(),
                }
            ]
            with self.subTest(member=member), self.assertRaises(ValueError):
                cargo_vendor.unpack(metadata, self.root / f"vendor-{index}", archive_root=self.root)
        self.assertFalse((self.root.parent / "escaped").exists())

    def test_vendor_checksum_metadata_matches_unpacked_files(self):
        data = crate_bytes()
        (self.root / "fixture_dep-0.1.0.crate").write_bytes(data)
        checksum = hashlib.sha256(data).hexdigest()
        cargo_vendor.unpack(
            [{"name": "fixture_dep", "version": "0.1.0", "checksum": checksum}],
            self.root / "vendor",
            archive_root=self.root,
        )
        root = self.root / "vendor/fixture_dep-0.1.0"
        metadata = json.loads((root / ".cargo-checksum.json").read_text())
        self.assertEqual(metadata["package"], checksum)
        for name, digest in metadata["files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)

    def test_download_plan_and_offline_build_bind_complete_lock(self):
        project = self.root / "project"
        project.mkdir()
        (project / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="0.1.0"\n')
        data = crate_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        (project / "Cargo.lock").write_text(
            'version=3\n[[package]]\nname="fixture_dep"\nversion="0.1.0"\nsource="registry+https://github.com/rust-lang/crates.io-index"\nchecksum="'
            + checksum
            + '"\n'
        )
        # Worker identity remains real; only the test's network transport is replaced.
        (self.root / "tui/src/jarvis_tui").mkdir(parents=True)
        for name in ("cargo_download.py", "cargo_vendor.py"):
            (self.root / "tui/src/jarvis_tui" / name).write_bytes(
                (Path(cargo_download.__file__).parent / name).read_bytes()
            )
        flow = OperationWorkflow(self.root)
        download = flow.propose(
            "development",
            "fetch_dependency",
            str(project),
            {"package": "fixture_dep", "version": "0.1.0"},
        )

        def process(argv, **kwargs):
            if argv[0] == "/usr/bin/bwrap":
                return {"status": "completed", "output": json.dumps(verify(self.root, argv[-1]))}
            Path(argv[-1]).write_bytes(data)
            return {
                "status": "completed",
                "output": json.dumps(
                    {"status": "downloaded", "sha256": checksum, "bytes": len(data), "attempts": 1}
                ),
            }

        with patch("jarvis_tui.operation_workflow.bounded_process", side_effect=process):
            result = flow.execute(flow.approve(download["id"], download["digest"]))
        self.assertTrue(result["verified"])
        build = flow.propose("development", "check", str(project), {"downloads": [download["id"]]})
        self.assertEqual(build["network"], "denied")
        self.assertEqual(build["crates"][0]["checksum"], checksum)
        Path(download["destination"]).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            flow.propose("development", "check", str(project), {"downloads": [download["id"]]})
