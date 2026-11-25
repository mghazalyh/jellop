import json
from pathlib import Path
import tempfile
import unittest
from config import Config, DEFAULT
from bridge import ffmpeg_args

class ConfigTests(unittest.TestCase):
    def test_revision_rollback_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"config.json"
            c=Config(p)
            self.assertEqual(c.snapshot(),DEFAULT)
            self.assertTrue(c.fault)
            first=dict(DEFAULT,revision=2,surfDwellSeconds=90,liveRingMiB=3,maxWidth=640,maxHeight=360,maxVideoBitrate=1000000)
            p.write_text(json.dumps(first))
            self.assertEqual(c.snapshot(),first)
            self.assertFalse(c.fault)
            for wrong in [dict(first,revision=1),dict(first,liveRingMiB=6),dict(first,revision=3,maxWidth=1920),dict(first,revision=3,surfDwellSeconds=True)]:
                p.write_text(json.dumps(wrong))
                self.assertEqual(c.snapshot(),first)
                self.assertTrue(c.fault)
            p.write_text('{"revision":2,"revision":3}')
            self.assertEqual(c.snapshot(),first)
            p.write_bytes(b"x"*4097)
            self.assertEqual(c.snapshot(),first)
            args=ffmpeg_args("ffmpeg","http://gateway/fixture",{},first)
            self.assertIn("scale=w=640:h=360:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",args)
            self.assertEqual(args[args.index("-b:v")+1],"1000000")
            rollback=dict(DEFAULT,revision=3)
            p.write_text(json.dumps(rollback))
            self.assertEqual(c.snapshot(),rollback)
            self.assertFalse(c.fault)

if __name__=="__main__":unittest.main()
