import unittest
from unittest.mock import Mock
from bridge import Bridge, Failure, client_token, filtered_channels, page_rows, hls_url, ffmpeg_args, media_source

CID="a"*32
OTHER="b"*32
TOKEN="test-token"

class BridgeTests(unittest.TestCase):
    def test_auth(self):
        self.assertEqual(client_token({"Authorization":'MediaBrowser Client="PS3", Token="test-token"'},{}),TOKEN)
        self.assertEqual(client_token({"X-Emby-Token":TOKEN},{}),TOKEN)
        with self.assertRaises(Failure):client_token({}, {})
    def test_bounded_page_and_filter(self):
        rows=[{"Id":CID,"Name":"Zulu","UserData":{"IsFavorite":True},"CurrentProgram":{"Name":"Film (2020)"}},
              {"Id":OTHER,"Name":"Alpha","ImageTags":{"Primary":"large"}}]
        self.assertEqual(page_rows(filtered_channels(rows,{}),{"limit":["1"]})["Items"][0]["Id"],OTHER)
        self.assertEqual(page_rows(filtered_channels(rows,{}),{"startindex":["1"],"limit":["1"]})["Items"][0]["Id"],CID)
        self.assertEqual(filtered_channels(rows,{"isfavorite":["true"]})[0]["Id"],CID)
        self.assertEqual(filtered_channels(rows,{"searchterm":["alp"]})[0]["Id"],OTHER)
        self.assertNotIn("CurrentProgram",filtered_channels(rows,{"addcurrentprogram":["false"],"ids":[CID]})[0])
        self.assertNotIn("ImageTags",filtered_channels(rows,{})[0])
        self.assertEqual(len(page_rows(list(range(500)),{"limit":["999"]})["Items"]),100)
    def test_media_path_and_output_bounds(self):
        path="/media/"+TOKEN+"/"+CID+".m3u8"
        self.assertEqual(hls_url("http://gateway",path,TOKEN),"http://gateway"+path)
        for invalid in ["http://other"+path,path+"?evil=1",path.replace(TOKEN,"other"),"/etc/passwd"]:
            with self.assertRaises(Failure):hls_url("http://gateway",invalid,TOKEN)
        args=ffmpeg_args("ffmpeg","http://gateway"+path,{"maxwidth":["7680"],"maxheight":["4320"],"videobitrate":["90000000"]})
        self.assertIn("scale=w=1280:h=720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",args)
        self.assertEqual(args[args.index("-b:v")+1],"4000000")
        self.assertEqual(args[args.index("-ac")+1],"2")
        self.assertEqual(args[args.index("-c:a")+1],"libmp3lame")
    def test_gateway_policy_is_authoritative_and_session_is_one_use(self):
        b=Bridge("http://gateway")
        b.upstream=Mock(side_effect=[{"Items":[{"Id":CID}]},
            {"PlaySessionId":OTHER,"MediaSources":[{"TranscodingUrl":"/media/"+TOKEN+"/"+CID+".m3u8"}]},
            {"Items":[{"Id":CID}]},
            {"Items":[]}])
        sid,source=b.resolve(TOKEN,CID)
        b.remember(TOKEN,CID,sid,source)
        self.assertEqual(b.resolve(TOKEN,CID,sid),(sid,source))
        self.assertNotIn((TOKEN,CID,sid),b.sessions)
        with self.assertRaises(Failure) as err:b.resolve(TOKEN,CID,sid)
        self.assertEqual(err.exception.status,409)
        self.assertEqual(b.upstream.call_count,4)
    def test_nonopening_probe_and_api(self):
        b=Bridge("http://gateway")
        b.upstream=Mock(return_value={"Items":[{"Id":CID,"Name":"Example","CurrentProgram":{"Name":"Movie"}}]})
        r=b.dispatch("POST","/Items/"+CID+"/PlaybackInfo",{"autoopenlivestream":["false"]},{"X-Emby-Token":TOKEN},b"{}")
        self.assertEqual(r["MediaSources"],[media_source(CID)])
        self.assertEqual(b.upstream.call_count,1)
        self.assertEqual(b.dispatch("GET","/LiveTv/Channels",{},{"X-Emby-Token":TOKEN},None)["Items"][0]["CurrentProgram"]["Name"],"Movie")
        with self.assertRaises(Failure):b.dispatch("GET","/unsupported",{},{"X-Emby-Token":TOKEN},None)

if __name__=="__main__":unittest.main()
