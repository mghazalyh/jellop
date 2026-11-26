import unittest
from surf_acceptance import evaluate
A="a"*32;B="b"*32
def fixture():
    lines=[];attempts=[]
    for i,cid in enumerate([A,B,A,B,A]):
        attempts.append((cid,200))
        lines.append(f"JELLOP_LIVE_CONFIRMED channel={cid} frame={i+1}")
        for sec in (1,3,15):
            lines.append(f"JELLOP_LIVE_SAMPLE channel={cid} frames={sec*30} decoded_ms={sec*1000} stalls=0 free_kib=12000 programme=Fixture Film {1 if cid==A else 2} (2020)")
        if i<4:lines.append(f"JELLOP_SURF_DUE from={cid} to={B if cid==A else A} cycle={(i+2)//2}")
    return "\n".join(lines),attempts
class AcceptanceTest(unittest.TestCase):
    def test_complete(self):
        lines,attempts=fixture()
        self.assertEqual(len(evaluate(lines,[A,B],attempts)["sessions"]),5)
    def test_missing_rollover(self):
        lines,attempts=fixture()
        self.assertIsNone(evaluate("\n".join(lines.splitlines()[:10]),[A,B],attempts[:2]))
    def test_excluded(self):
        lines,attempts=fixture()
        with self.assertRaises(RuntimeError):evaluate(lines,[A,B],attempts+[("d"*32,200)])
    def test_wrong_cycle(self):
        lines,attempts=fixture()
        with self.assertRaises(RuntimeError):evaluate(lines.replace("cycle=2","cycle=1"),[A,B],attempts)
    def test_missing_title(self):
        lines,attempts=fixture()
        with self.assertRaises(RuntimeError):evaluate(lines.replace("Fixture Film 1 (2020)",""),[A,B],attempts)
    def test_stall(self):
        lines,attempts=fixture()
        with self.assertRaises(RuntimeError):evaluate(lines.replace("stalls=0","stalls=1"),[A,B],attempts)
if __name__=="__main__":unittest.main()
