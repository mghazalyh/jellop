import unittest
from unittest.mock import Mock
from bridge import Bridge,Failure,authoritative_catalogue,filtered_channels,hls_url
A="a"*32; B="b"*32; C="c"*32
def data():
    return {"Items":[{"Id":A,"Name":"Unrelated","Tags":["Sports"]},
        {"Id":B,"Name":"Sports by name only","Genres":["Drama"]},
        {"Id":C,"Name":"Third"}],"JealousfinPolicy":{"revision":"sqlite-policy-v2","channels":{
        A:{"banned":False,"hiatusUntil":0},B:{"banned":False,"hiatusUntil":4102444800},
        C:{"banned":True,"hiatusUntil":0}}}}
class PolicyParity(unittest.TestCase):
    def test_strict_membership_and_categories(self):
        rows=authoritative_catalogue(data(),now=1795620000)
        self.assertEqual([r["JellopGenreMask"] for r in rows],[2,4,0])
        self.assertEqual([r["JellopHealth"]["eligible"] for r in rows],[True,False,False])
        b=Bridge("http://gateway");b.upstream=Mock(return_value=data())
        self.assertEqual([r["Id"] for r in b.catalogue("token")],[A])
        excluded=b.dispatch("GET","/Jellop/ChannelPolicy",{},{"X-Emby-Token":"token"},None)
        self.assertEqual({r["Id"] for r in excluded["Items"]},{B,C})
        with self.assertRaises(Failure) as e:b.eligible("token",B)
        self.assertEqual(e.exception.status,409)
    def test_missing_or_invalid_policy_fails_closed(self):
        for mutate in (lambda d:d.pop("JealousfinPolicy"),lambda d:d["JealousfinPolicy"]["channels"].pop(A),
                       lambda d:d["Items"].append(d["Items"][0]),lambda d:d["JealousfinPolicy"]["channels"][A].update(banned="false"),
                       lambda d:d["JealousfinPolicy"]["channels"][A].update(hiatusUntil=float("nan"))):
            d=data();mutate(d)
            with self.assertRaises(Failure) as e:authoritative_catalogue(d)
            self.assertEqual(e.exception.status,503)
    def test_malay_stream_path(self):
        self.assertEqual(hls_url("http://gateway","/malay/media/token/"+A+".m3u8","token"),"http://gateway/malay/media/token/"+A+".m3u8")
        with self.assertRaises(Failure):hls_url("http://gateway","/malay/media/other/"+A+".m3u8","token")
if __name__=="__main__":unittest.main()
