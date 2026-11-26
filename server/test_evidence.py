import json
import unittest
from unittest.mock import patch,Mock
from bridge import Bridge

CID="a"*32
SID="b"*32
TOKEN="fixture-token"

class EvidenceTests(unittest.TestCase):
    def sample(self,b,t,frames,ms,stalls=0,paused=False,token=TOKEN):
        with patch("bridge.time.monotonic",return_value=t):
            b.report_evidence(token,{"ItemId":CID,"PlaySessionId":SID,"IsPaused":paused,
                "JellopEvidence":{"Version":1,"Frames":frames,"DecodedMs":ms,"Stalls":stalls,
                "FreeKiB":10000,"RingPackets":100,"RingCapacity":1000}})
    def test_sustained_is_decoded_not_network(self):
        b=Bridge("http://gateway",require_policy=False);b.upstream=Mock(return_value={"Items":[]})
        self.sample(b,0,0,0)
        self.assertEqual(len(b.evidence),0)
        b.stream_started(TOKEN,CID,SID)
        for i in range(7):self.sample(b,10*i,250*i,10000*i)
        row=b.evidence[(TOKEN,CID,SID)]
        self.assertTrue(row["sustained"]);self.assertEqual(row["samples"],7)
        self.sample(b,61,1700,61000);self.assertEqual(row["samples"],7)
        self.sample(b,70,1750,70000,1);self.assertEqual(row["run_seconds"],0)
        self.sample(b,80,2000,80000,1,token="another");self.assertEqual(row["samples"],8)
        b.stream_finished(TOKEN,CID,SID,"client-disconnected")
        self.sample(b,90,2250,90000,1);self.assertEqual(row["samples"],8)
        self.assertEqual(b.diagnostics("another")["Sessions"],[])
        self.assertFalse(b.diagnostics(TOKEN)["PolicyMutation"])
        self.assertEqual(b.upstream.call_count,2)
    def test_bad_samples_and_bounded_storage(self):
        b=Bridge("http://gateway",require_policy=False)
        for i in range(30):b.stream_started(TOKEN,CID,f"{i:032x}")
        self.assertEqual(len(b.evidence),24)
        b.stream_started(TOKEN,CID,SID)
        self.sample(b,0,0,0);self.sample(b,10,0,10000);self.sample(b,20,250,30000)
        row=b.evidence[(TOKEN,CID,SID)];self.assertFalse(row["sustained"])
        self.assertEqual(row["run_seconds"],0)
    def test_report_strips_private_extension(self):
        b=Bridge("http://gateway",require_policy=False)
        b.upstream=Mock(return_value={})
        b.stream_started(TOKEN,CID,SID)
        data={"ItemId":CID,"PlaySessionId":SID,"IsPaused":False,
              "JellopEvidence":{"Version":1,"Frames":200,"DecodedMs":8000,"Stalls":0,
              "FreeKiB":10000,"RingPackets":100,"RingCapacity":1000}}
        b.dispatch("POST","/Sessions/Playing/Progress",{},{"X-Emby-Token":TOKEN},json.dumps(data).encode())
        self.assertNotIn("JellopEvidence",json.loads(b.upstream.call_args.args[3]))
        self.assertEqual(b.evidence[(TOKEN,CID,SID)]["samples"],1)

if __name__=="__main__":unittest.main()
