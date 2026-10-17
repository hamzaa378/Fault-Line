"""Run against a started Faultline stack. Demonstrates out-of-order, duplicates and evidence."""
import os, requests
from datetime import datetime, timedelta, timezone
from uuid import uuid4
BASE = os.getenv('FAULTLINE_API', 'http://localhost:8000')
EMAIL = os.getenv('FAULTLINE_EMAIL', 'alex@faultline.dev')
PASSWORD = os.getenv('SEED_PASSWORD', 'DemoPassword123!')

def call(method, path, **kw):
    r = requests.request(method, BASE+path, timeout=15, **kw)
    print(f'{method:>5} {path}: {r.status_code}')
    if r.status_code >= 400: raise RuntimeError(r.text)
    return r.json()

token = call('POST','/api/auth/login',json={'email':EMAIL,'password':PASSWORD})['access_token']
headers = {'Authorization':'Bearer '+token}
pid = call('GET','/api/projects',headers=headers)[0]['id']
p = f'/api/projects/{pid}'
now = datetime.now(timezone.utc)
sha = uuid4().hex
version = 'demo-'+sha[:7]
call('POST',p+'/changes',headers=headers,json={'sha':sha,'title':'Test release from demo script','author':'Demo CI','service':'checkout-api','committed_at':(now-timedelta(minutes=17)).isoformat(),'changed_files':['src/checkout.py']})
dep = call('POST',p+'/deployments',headers=headers,json={'version':version,'service':'checkout-api','status':'success','commit_sha':sha,'deployed_at':(now-timedelta(minutes=9)).isoformat()})
inc = call('POST',p+'/incidents',headers=headers,json={'title':'Demo checkout latency increase','service':'checkout-api','severity':'SEV2','first_seen_at':now.isoformat()})
print('Top suspect:',call('GET',p+f'/incidents/{inc["id"]}/suspects',headers=headers)['candidates'][0]['version'])
external_id = 'demo-alert-'+sha[:7]
body={'source':'monitor','external_id':external_id,'type':'alert','summary':'Late alert from upstream monitor','occurred_at':(now-timedelta(hours=2)).isoformat(),'details':{'severity':'high'}}
call('POST',p+'/events/ingest',headers=headers,json=body)
assert call('POST',p+'/events/ingest',headers=headers,json=body)['duplicate']
print('DEMO COMPLETE. Compare /events?order=received vs /events?order=occurred.')
