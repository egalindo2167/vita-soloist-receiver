import io
import json
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pc'))
import soloist_bridge as bridge
import favorites

TRACK='spotify:track:'+'A'*22
def item():
    return {'uri':TRACK,'decorations':{'identity':{'name':'Canción de prueba'},
        'creators':[{'entity':{'decorations':{'identity':{'name':'Test artist'}}}}],
        'parent':{'entity':{'decorations':{'identity':{'name':'Test album'}}}},
        'playback':{'duration_ms':210000},
        'visual_identity':{'cover':[{'url':'https://i.scdn.co/image/test','size':'default'}]}}}
def player():
    p=bridge.Player(); p.update({'type':'auth_state','logged_in':True,'is_active':True})
    p.update({'type':'playback_state','status':'playing','item':item(),'is_active':True,
              'volume':65,'position':{'position_ms':45000,'timestamp_ms':1000000,'speed':1},
              'options':{'shuffle':False,'repeat':'off'}})
    return p

class ControlBridgeTests(unittest.TestCase):
    def test_documented_metadata_shape_and_binary_layout(self):
        p=player()
        self.assertEqual(p.item['artist'],'Test artist')
        self.assertEqual(p.item['album'],'Test album')
        with mock.patch.object(bridge.time,'time',return_value=1002): raw=p.state_payload()
        self.assertEqual(len(raw),908)
        fields=struct.unpack_from('<11I',raw)
        self.assertEqual(fields[:10],(1,1,1,1,1,65,0,0,47000,210000))
        self.assertEqual(raw[44:236].split(b'\0')[0].decode(),'Canción de prueba')
    def test_paused_position_does_not_advance(self):
        p=player(); p.update({'type':'playback_changed','status':'paused'})
        self.assertEqual(p.position_ms(now=5000),45000)
        self.assertEqual(p.commands(1,0,'')[0]['command'],'play')
    def test_controls_and_repeat_clear_the_other_flag_first(self):
        p=player()
        self.assertEqual(p.commands(1,0,'')[0]['command'],'pause')
        self.assertEqual(p.commands(4,100,'')[0]['volume'],100)
        self.assertEqual(p.commands(4,-200,'')[0]['volume'],0)
        self.assertTrue(p.commands(6,0,'')[0]['enabled'])
        self.assertEqual(p.commands(7,0,''),[
            {'type':'command','command':'set_repeat_track','enabled':False},
            {'type':'command','command':'set_repeat_context','enabled':True}])
        self.assertEqual(p.commands(7,0,'')[-1],{'type':'command','command':'set_repeat_track','enabled':True})
        self.assertFalse(p.commands(7,0,'')[-1]['enabled'])
        self.assertEqual(p.commands(10,999999,'')[0]['position_ms'],210000)
    def test_song_selection_requires_auth_and_valid_spotify_uri(self):
        p=bridge.Player()
        with self.assertRaisesRegex(ValueError,'Pair'): p.commands(8,0,TRACK)
        p=player(); p.active=False
        self.assertEqual([c['command'] for c in p.commands(8,0,TRACK)],['activate','play'])
        with self.assertRaises(ValueError): p.commands(8,0,'file:///private/file')
    def test_queue_and_fixed_strings_are_bounded_without_broken_utf8(self):
        p=player(); p.update({'type':'queue_changed','upcoming':[{'item':item()}]*80})
        self.assertEqual(len(p.queue),80)
        self.assertEqual(len(bridge.list_payload(p.queue)),4+32*384)
        for size in range(1,20):
            result=bridge.fixed('é'*40,size)
            self.assertEqual(len(result),size)
            result.split(b'\0')[0].decode('utf-8','strict')
    def test_fragmented_command_frames_and_bad_lengths(self):
        payload=struct.pack('<Ii',4,-5)+bridge.fixed('',128)
        raw=bridge.packet(b'CMND',payload)*2
        frames=bridge.Frames(); decoded=[]
        for start in range(0,len(raw),3): decoded.extend(frames.feed(raw[start:start+3]))
        self.assertEqual(decoded,[(4,-5,''),(4,-5,'')])
        with self.assertRaises(ValueError): bridge.Frames().feed(struct.pack('<4sI',b'CMND',999999))
    def test_new_receiver_diagnostics_keep_route_and_bitrate_and_accept_legacy_reports(self):
        values=[];frames=bridge.Frames(values.append)
        wire=struct.pack('<4sI6I',b'RSTA',24,1,469,10,1,128,1)+struct.pack('<4sI4I',b'RSTA',16,2,256,20,1)+struct.pack('<4sI7I',b'RSTA',28,3,1024,30,1,320,1,3)
        for at in range(0,len(wire),3):self.assertEqual(frames.feed(wire[at:at+3]),[])
        self.assertEqual(values,[(1,469,10,1,128,1),(2,256,20,1),(3,1024,30,1,320,1,3)])
    def test_favorites_urls_and_atomic_cli_output(self):
        url='https://open.spotify.com/intl-es/track/'+'A'*22+'?si=test'
        self.assertEqual(favorites.spotify_uri(url),TRACK)
        with self.assertRaises(ValueError): favorites.spotify_uri('https://example.org/track/'+'A'*22)
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/'favorites.json'
            with mock.patch.object(favorites,'DEFAULT_PATH',path), \
                 mock.patch.object(favorites,'load_favorites',return_value=[]):
                self.assertEqual(favorites.main(['add',url,'--name','My song']),0)
            self.assertEqual(favorites.load_favorites(path)[0]['title'],'My song')
    def test_rgb565_artwork_conversion_and_source_validation(self):
        from PIL import Image
        file=io.BytesIO(); Image.new('RGB',(8,8),(255,0,0)).save(file,format='PNG')
        response=mock.MagicMock(); response.__enter__.return_value=response
        response.read.return_value=file.getvalue()
        opener=mock.Mock();opener.open.return_value=response
        with mock.patch.object(bridge,'build_opener',return_value=opener):
            art=bridge.download_art('https://i.scdn.co/image/test')
        self.assertEqual(len(art),224*224*2)
        self.assertEqual(struct.unpack_from('<H',art)[0],0xf800)
        with self.assertRaises(ValueError): bridge.download_art('http://127.0.0.1/private')
    def test_endpoint_only_reads_local_soloist_address(self):
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)
            (path/'ws.addr').write_text('127.0.0.1'); (path/'ws.port').write_text('9090')
            self.assertEqual(bridge.endpoint(path),'ws://127.0.0.1:9090')
            (path/'ws.addr').write_text('0.0.0.0')
            with self.assertRaises(ValueError): bridge.endpoint(path)

if __name__=='__main__': unittest.main()
