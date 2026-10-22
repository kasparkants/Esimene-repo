import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
import struct

import recovery


def png():
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    return (recovery.SIGNATURES['png']
            + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b''))


class RecoveryTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(Path(recovery.__file__)), *map(str, args)],
                              capture_output=True, text=True, timeout=20)

    def test_scan_and_recover_image_without_modifying_source(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('example.txt', 'recovered content')
            out.comment = b'archive comment'
        contents = [('png', png()), ('pdf', b'%PDF-1.4\nexample\n%%EOF'),
                    ('jpg', b'\xff\xd8\xff\xe0example\xff\xd9'), ('zip', archive.getvalue())]
        image = b'\x00' * (recovery.CHUNK - 3)
        expected = {}
        for kind, data in contents:
            expected[(len(image), kind)] = data
            image += data + b'\x00' * 128
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'disk.img'
            source.write_bytes(image)
            before = hashlib.sha256(image).digest()
            result = self.run_cli(source, '--recover', Path(folder) / 'recovered')
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(rows[-1]['candidates'], 4)
            for row in rows[:-1]:
                self.assertEqual(Path(row['saved_to']).read_bytes(), expected[(row['offset'], row['format'])])
                if row['format'] == 'zip':
                    self.assertTrue(row['zip_directory_valid'])
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)

    def test_scan_only_creates_no_files_and_reports_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'disk.img'
            source.write_bytes(b'\x00' * 40 + b'%PDF-1.7\ntruncated')
            result = self.run_cli(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(result.stdout.splitlines()[0])
            self.assertEqual(row['status'], 'incomplete-or-false-positive')
            self.assertEqual(list(Path(folder).iterdir()), [source])

    def test_range_and_candidate_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'disk.img'
            source.write_bytes(b'%PDF-1\n%%EOF' * 4)
            result = self.run_cli(source, '--max-candidates', '1')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout.splitlines()[-1])['candidate_limit_reached'])
            result = self.run_cli(source, '--start', '1', '--length', '4')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['candidates'], 0)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'disk.img'
            source.write_bytes(png())
            result = self.run_cli(source, '--recover', folder)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_bytes(), png())

    def test_maximum_file_size_bounds_search(self):
        stream = io.BytesIO(b'%PDF-' + b'a' * 100 + b'%%EOF')
        self.assertIsNone(recovery.extent(stream, 0, 'pdf', 20, None))

    def test_aligned_reader_supports_unaligned_logical_reads(self):
        data = bytes(range(256)) * 40
        stream = recovery.AlignedReader(io.BytesIO(data))
        stream.seek(17)
        self.assertEqual(stream.read(4200), data[17:4217])
        self.assertEqual(stream.read(1), data[4217:4218])

    def test_failed_copy_does_not_leave_complete_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'file.jpg'
            with self.assertRaises(OSError):
                recovery.carve(io.BytesIO(b'x'), 0, 10, target)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
