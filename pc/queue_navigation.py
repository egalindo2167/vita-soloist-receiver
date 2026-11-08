"""Stable queue windows and context-preserving selection through serial skips.

Soloist has no documented jump-to-queue-entry command or response IDs. A short
broadcast is merged by entry identity; an explicit short snapshot is debounced
so a 10-item broadcast preceding the full local reply cannot flash a short list.
"""
import hashlib
import time
import unicodedata
from favorites import spotify_uri

LIMIT=10000  # PC safety bound, not a claim about Soloist's available queue.

class QueueCache:
    def __init__(self):
        self.items=[];self.context='';self.serial=0;self.awaiting=False;self.needs_query=False
        self.candidate=None;self.commit_at=0.
        self.source_count=0;self.truncated=False;self.revision=0
    def reset(self,context=''):
        self.items=[];self.context=context;self.serial+=1;self.awaiting=False;self.candidate=None;self.needs_query=True
        self.source_count=0;self.truncated=False;self.revision+=1
    def request(self,now=None):
        self.awaiting=True;self.needs_query=False;self.candidate=None
    def update(self,entries,convert,now=None):
        now=time.monotonic() if now is None else now
        if not isinstance(entries,list):return
        source_count=len(entries)
        counts={};new=[];uids=set()
        for entry in entries[:LIMIT]:
            if not isinstance(entry,dict):continue
            value=convert(entry.get('item'))
            try:value['uri']=spotify_uri(value['uri'])
            except ValueError:continue
            uri=value['uri'];ordinal=counts.get(uri,0);counts[uri]=ordinal+1
            uid=entry.get('uid');stable=isinstance(uid,str) and 0<len(uid)<=512 and uid!=uri and uid not in uids
            if stable:uids.add(uid)
            key='uid:'+uid if stable else 'uri:'+uri+'#'+str(ordinal)
            token='q:'+hashlib.sha256((self.context+'\0'+key).encode()).hexdigest()[:32]
            value.update(key=key,stable=stable,selection=token);new.append(value)
        self.serial+=1
        if len(new)!=10:
            self._commit(new,source_count);self.awaiting=False;self.candidate=None;self.needs_query=False;return
        old=self.items;merged=new
        # Retain only a tail anchored by at least two consecutive stable entries.
        # Reorders/context changes without an overlap never invent a tail.
        for length in range(min(10,len(old)),1,-1):
            suffix=[e['key'] for e in new[-length:]]
            found=next((i for i in range(len(old)-length+1) if [e['key'] for e in old[i:i+length]]==suffix),None)
            if found is not None:
                seen={e['key'] for e in new};tail=[e for e in old[found+length:] if e['key'] not in seen]
                merged=(new+tail)[:LIMIT];break
        self._commit(merged,max(source_count,len(merged),self.source_count if len(merged)>10 else 0))
        if self.awaiting:
            self.candidate=new;self.commit_at=now+.35
        else:self.needs_query=True
    def tick(self,now=None):
        now=time.monotonic() if now is None else now
        if self.candidate is not None and now>=self.commit_at:
            self._commit(self.candidate,len(self.candidate));self.candidate=None;self.awaiting=False
    def _commit(self,items,source_count):
        if items!=self.items or source_count!=self.source_count:self.revision+=1
        self.items=items;self.source_count=source_count;self.truncated=source_count>LIMIT
    def resolve(self,token):
        matches=[(i,e) for i,e in enumerate(self.items) if e['selection']==token]
        if len(matches)!=1:raise ValueError('Queue changed. Refresh and select the song again.')
        return matches[0]

def search_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold())
                   if not unicodedata.combining(c))

class QueueSearch:
    """PC-only index with bounded five-row encrypted replies, never a playlist scraper."""
    def __init__(self):
        self.request_id=0;self.query='';self.offset=0;self.revision=-1;self.matches=[]
        self.index=[];self.index_revision=-1
    def search(self,request_id,query):
        if not 1<=request_id<=0x7fffffff:raise ValueError('Invalid queue search request')
        if len(query.encode('utf-8'))>127 or any(ord(c)<32 or ord(c)==127 for c in query):
            raise ValueError('Invalid queue search text')
        self.request_id=request_id;self.query=query;self.offset=0;self.revision=-1
    def page(self,request_id,offset):
        if request_id!=self.request_id:return False
        if not 0<=offset<LIMIT or offset%5:raise ValueError('Invalid queue page')
        self.offset=offset;return True
    def results(self,cache):
        if cache.revision!=self.index_revision:
            self.index=[search_key(str(e.get('title',''))+' '+str(e.get('artist',''))) for e in cache.items]
            self.index_revision=cache.revision
        if cache.revision!=self.revision:
            words=search_key(self.query).split()
            self.matches=[i for i,text in enumerate(self.index) if all(w in text for w in words)]
            self.revision=cache.revision
        total=len(self.matches)
        if self.offset>=total:self.offset=(max(0,total-1)//5)*5
        return [(i+1,cache.items[i]) for i in self.matches[self.offset:self.offset+5]],total

class QueueJump:
    """Send one skip, wait for actual current-item AND queue advancement, repeat.

    Acceptance is not completion. No play(uri), synthetic replacement queue, or
    burst of skip commands is used. Duplicate tracks require stable entry IDs.
    """
    def __init__(self):self.active=False;self.path=[];self.queried=False;self.done=0;self.total=0
    def start(self,token,player,now=None):
        now=time.monotonic() if now is None else now
        if not player.logged:raise ValueError('Pair the bridge by selecting it in Spotify first.')
        if not player.active:raise ValueError('Activate Soloist and refresh its queue first.')
        index,_=player.queue_cache.resolve(token)
        if index>=256:raise ValueError('This song is over 256 skips away. Select it in Spotify; no skips were sent.')
        items=player.queue_cache.items
        uris=[e['uri'] for e in items]
        if len(set(uris))<len(uris) and any(not e['stable'] for e in items):
            raise ValueError('Duplicate queue tracks need stable Soloist entry IDs. Use Next for this queue.')
        self.path=list(items[:index+1]);self.total=len(self.path);self.done=0
        self.resume_after=player.status!='playing'
        self.context=player.context;self.started=now;self.active=True
        self.deadline=now+max(20,min(120,self.total*1.5+10))
        return self._issue(player,now)
    def _issue(self,player,now):
        self.since=now;self.serial=player.queue_cache.serial;self.before_uri=player.item['uri'];self.queried=False
        return [{'type':'command','command':'skip_next'}]
    def cancel(self):self.active=False;self.path=[]
    @property
    def message(self):return f'Advancing queue: {min(self.done+1,self.total)}/{self.total}'
    def advance(self,player,now=None):
        now=time.monotonic() if now is None else now
        if not self.active:return []
        if player.context!=self.context:
            self.cancel();raise ValueError('Playback context changed; queue selection stopped.')
        expected=self.path[0];cache=player.queue_cache
        keys={e['key'] for e in cache.items}
        if cache.serial>self.serial and expected['key'] not in keys and player.item['uri']==expected['uri']:
            if now-self.since<.08:return [] # Bound Connect command cadence even with very fast replies.
            self.path.pop(0);self.done+=1
            if not self.path:
                self.active=False
                return [{'type':'command','command':'play'}] if self.resume_after else []
            if not cache.items or cache.items[0]['key']!=self.path[0]['key']:
                self.cancel();raise ValueError('Queue changed during selection. Refresh and try again.')
            return self._issue(player,now)
        if player.item['uri'] not in (self.before_uri,expected['uri']):
            self.cancel();raise ValueError('Another playback change interrupted queue selection.')
        if now>self.deadline or now-self.since>6:
            self.cancel();raise ValueError('Queue skip was not confirmed. Refresh and try again.')
        if now-self.since>2 and not self.queried:
            self.queried=True
            return [{'type':'command','command':'get_state'},{'type':'command','command':'get_queue','limit':0}]
        return []
