import unittest
from surf_acceptance import evaluate, evaluate_controls
A="a"*32;B="b"*32
def fixture(transitions=4):
    lines=[];attempts=[]
    for i,cid in enumerate([A if i%2==0 else B for i in range(transitions+1)]):
        attempts.append((cid,200))
        lines.append(f"JELLOP_LIVE_CONFIRMED channel={cid} frame={i+1}")
        for sec in (1,3,15):
            lines.append(f"JELLOP_LIVE_SAMPLE channel={cid} frames={sec*30} decoded_ms={sec*1000} stalls=0 free_kib=12000 programme=Fixture Film {1 if cid==A else 2} (2020)")
        if i<transitions:lines.append(f"JELLOP_SURF_DUE from={cid} to={B if cid==A else A} cycle={1+(i+1)//2}")
    return "\n".join(lines),attempts
class AcceptanceTest(unittest.TestCase):
    def test_complete(self):
        lines,attempts=fixture()
        self.assertEqual(len(evaluate(lines,[A,B],attempts)["sessions"]),5)
    def test_endurance(self):
        lines,attempts=fixture(20)
        result=evaluate(lines,[A,B],attempts,transitions=20)
        self.assertEqual(result["completed_cycles"],10)
        self.assertEqual(len(result["sessions"]),21)
        self.assertEqual(result["guest_memory_drop_kib"],0)
    def test_low_memory(self):
        lines,attempts=fixture()
        with self.assertRaises(RuntimeError):evaluate(lines.replace("free_kib=12000","free_kib=8191"),[A,B],attempts)
    def test_memory_drift(self):
        lines,attempts=fixture()
        chunks=lines.splitlines()
        chunks[:4]=[s.replace("free_kib=12000","free_kib=18000") for s in chunks[:4]]
        with self.assertRaises(RuntimeError):evaluate("\n".join(chunks),[A,B],attempts)
    def test_invalid_transition_budget(self):
        lines,attempts=fixture()
        for n in (0,3,5,26):
            with self.assertRaises(ValueError):evaluate(lines,[A,B],attempts,transitions=n)
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
class ControlsTest(unittest.TestCase):
    def test_round_trip(self):
        lines="JELLOP_SMOKE_POLICY banned=1 hiatus=1 playable=0\nJELLOP_SMOKE_FAVOURITE value=1\nJELLOP_SMOKE_FAVOURITE value=0"
        self.assertTrue(evaluate_controls(lines,[(A,True),(A,False)],[],A)["favourite_round_trip"])
    def test_incomplete(self):
        self.assertIsNone(evaluate_controls("",[(A,True)],[A],A))
    def test_wrong_identity(self):
        with self.assertRaises(RuntimeError):evaluate_controls("",[(B,True)],[],A)
    def test_failed_native(self):
        with self.assertRaises(RuntimeError):evaluate_controls("JELLOP_SMOKE_CONTROL_FAIL",[],[],A)
    def test_failed_persistence(self):
        with self.assertRaises(RuntimeError):evaluate_controls("",[(A,True),(A,False)],[A],A)
if __name__=="__main__":unittest.main()
