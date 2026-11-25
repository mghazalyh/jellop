import socket
import unittest
from unittest.mock import Mock
from bridge import Bridge, Failure, ActiveStream

CID="a"*32
SID="b"*32
TOKEN="fixture-token"

class StopTests(unittest.TestCase):
    def test_scope_and_release(self):
        b=Bridge("http://gateway")
        sock=Mock();proc=Mock()
        active=b.claim_stream(TOKEN,CID,SID,sock)
        self.assertTrue(active.attach(proc))
        self.assertFalse(b.transcode.acquire(blocking=False))
        b.remember(TOKEN,CID,SID,"http://gateway/media")
        # Unknown ownership or session cannot cancel the active transcode.
        b.stop_stream("other",SID);b.stop_stream(TOKEN,"c"*32)
        proc.terminate.assert_not_called();sock.shutdown.assert_not_called()
        # Completion is signalled by the streaming handler, never by DELETE.
        active.done.set()
        result=b.dispatch("DELETE","/Videos/ActiveEncodings",{"playsessionid":[SID]},
                          {"X-Emby-Token":TOKEN},None)
        self.assertEqual(result,{})
        self.assertTrue(active.cancelled.is_set())
        proc.terminate.assert_called_once()
        sock.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        self.assertNotIn((TOKEN,CID,SID),b.sessions)
        self.assertFalse(b.transcode.acquire(blocking=False))
        b.release_stream(active)
        self.assertTrue(b.transcode.acquire(blocking=False));b.transcode.release()
        self.assertIsNone(b.active)

    def test_cancel_before_process_spawn(self):
        control=ActiveStream(TOKEN,CID,SID,Mock())
        control.cancel()
        proc=Mock()
        self.assertFalse(control.attach(proc))
        proc.terminate.assert_called_once()

    def test_invalid_session(self):
        b=Bridge("http://gateway")
        with self.assertRaises(Failure) as e:b.stop_stream(TOKEN,"bad")
        self.assertEqual(e.exception.status,400)

if __name__=="__main__":unittest.main()
