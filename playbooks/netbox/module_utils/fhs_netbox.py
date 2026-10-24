"""Small shared API client for the portable hardware/manufacturer helpers."""
import re
import hashlib
import json
from urllib.parse import urljoin
import requests

def scalar(value):
    if isinstance(value,dict):
        return value.get('id',value.get('value',value))
    return value


class Sync:
    def __init__(self,params,check):
        self.url=params['netbox_url'].rstrip('/')+'/api/'
        self.check=check;self.plan=[];self.virtual=-1;self.cache={};self.deleted=set()
        self.session=requests.Session();self.session.verify=params['validate_certs']
        token=params['netbox_token'];self.session.headers.update(Authorization=('Bearer ' if token.startswith('nbt_') else 'Token ')+token)
    def request(self,method,path,**kwargs):
        response=self.session.request(method,self.url+path,timeout=30,**kwargs)
        if not response.ok:raise ValueError(f'NetBox {method} {path} failed with HTTP {response.status_code}; inspect the plan and parent journal before retrying')
        if method not in ('GET', 'OPTIONS'): self.cache.clear()
        if response.status_code == 204: return None
        return response.json()
    def list(self, path, **filters):
        if any(isinstance(v,int) and v<0 for v in filters.values()): return []
        rows=[]; url=path; seen=set(); kwargs={'params':dict(filters,limit=100)}
        while url:
            if url in seen: raise ValueError('Repeated NetBox pagination URL')
            seen.add(url)
            data=self.request('GET',url,**kwargs); rows.extend(row for row in data['results'] if (path,row['id']) not in self.deleted)
            next_url=data.get('next'); kwargs={}
            if next_url:
                absolute=urljoin(self.url+url,next_url)
                if not absolute.startswith(self.url): raise ValueError('Refuse foreign NetBox pagination URL')
                url=absolute[len(self.url):]
            else: url=None
        return rows
    def find(self,path,**filters):
        key=(path,tuple(sorted(filters.items())))
        if key in self.cache:return self.cache[key]
        rows=self.list(path,**filters)
        if len(rows)>1:raise ValueError('Ambiguous NetBox object at '+path)
        value=rows[0] if rows else None
        self.cache[key]=value
        return value
    def delete(self,path,old,label):
        self.plan.append(dict(object=label,action='delete',before=old,after={}))
        if not self.check: self.request('DELETE',path+str(old['id'])+'/')
        self.deleted.add((path,old['id']))
        self.cache.clear()
    def journal(self,device,bay,old_serial,new_serial,result,**details):
        data={'assigned_object_type':'dcim.device','assigned_object_id':device,
              'kind':'info','comments':json.dumps(dict(importer='fhs',bay=bay,
                  old_serial=old_serial,new_serial=new_serial,result=result,**details),sort_keys=True)}
        self.plan.append(dict(object=bay+' journal',action='create',before={},after=data))
        if not self.check: self.request('POST','extras/journal-entries/',json=data)
    def ensure(self,path,key,data,label):
        old=self.find(path,**key)
        changed={k:v for k,v in data.items() if (scalar(old.get(k)) if old else None)!=v}
        if 'custom_fields' in data and old:
            merged=dict(old.get('custom_fields') or {},**data['custom_fields'])
            changed.pop('custom_fields',None)
            if merged!=old.get('custom_fields'):changed['custom_fields']=merged
        if not changed:return old
        self.plan.append(dict(object=label,action='update' if old else 'create',before={k:old.get(k) for k in changed} if old else {},after=changed))
        if self.check:
            if old:result=dict(old,**changed)
            else:
                self.virtual-=1;result=dict(data,id=self.virtual)
        else:result=self.request('PATCH',path+str(old['id'])+'/',json=changed) if old else self.request('POST',path,json=data)
        self.cache[(path,tuple(sorted(key.items())))]=result
        return result


def ensure_manufacturers(sync,names):
    records={}
    for name in dict.fromkeys(value.strip() for value in names):
        if not name:raise ValueError('Manufacturer name cannot be empty')
        existing=sync.find('dcim/manufacturers/',name=name)
        if existing:
            records[name]=existing;continue
        slug=re.sub('[^a-z0-9]+','-',name.lower()).strip('-')[:100] or 'manufacturer'
        owner=sync.find('dcim/manufacturers/',slug=slug)
        if owner and owner['name'].strip().casefold()==name.casefold():
            records[name]=owner;continue
        if owner:
            slug=slug[:90]+'-'+hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]
            collision=sync.find('dcim/manufacturers/',slug=slug)
            if collision and collision['name']!=name:
                raise ValueError('Deterministic manufacturer slug collision; review vendor records')
        records[name]=sync.ensure('dcim/manufacturers/',{'name':name},{'name':name,'slug':slug},name+' manufacturer')
    return records


ASSETS = 'plugins/inventory/assets/'
UNKNOWN_SERIALS = {'', 'unknown', 'none', 'n/a', 'not specified', 'not available', 'to be filled by o.e.m.', 'default string', 'to be filled by o.e.m', 'to be filled by oem', 'system serial number', 'chassis serial number', 'not applicable', 'unavailable'}


def physical_serial(value):
    value=str(value or '').strip()
    if value.lower() in UNKNOWN_SERIALS or re.sub(r'[^a-z0-9]', '', value.lower()).startswith('tobefilledbyoem'): raise ValueError('Physical serial is missing or unavailable; preserve existing inventory')
    return value


def physical_device(sync, name, serial, allow_missing=False):
    """Resolve stable chassis identity without changing hostname or inventory."""
    if allow_missing and not str(serial or '').strip():
        return sync.find('dcim/devices/',name=name)
    serial=physical_serial(serial)
    by_serial=sync.find('dcim/devices/',serial=serial)
    by_name=sync.find('dcim/devices/',name=name)
    if by_serial and by_name and by_serial['id']!=by_name['id']:
        raise ValueError('Hostname and chassis serial identify different devices')
    device=by_serial or by_name
    if device and device.get('serial') and device['serial']!=serial:
        raise ValueError('Chassis serial differs; review physical device replacement explicitly')
    return device


def asset_candidate(sync, kind, type_id, serial, hardware_id=None):
    """Serial identity within the actual hardware type; never rewrite an asset."""
    serial=physical_serial(serial)
    matches=sync.list(ASSETS,serial=serial,**{kind+'_type_id':type_id})
    # Verify response identity too: an unsupported/ignored filter must not move assets.
    matches=[a for a in matches if a.get('serial')==serial and scalar(a.get(kind+'_type'))==type_id]
    if len(matches)>1: raise ValueError('Ambiguous asset serial/type identity')
    asset=matches[0] if matches else None
    if asset:
        if scalar(asset.get('status'))=='faulty': raise ValueError('Quarantined asset requires explicit review before installation')
        if scalar(asset.get(kind)) not in (None,hardware_id): raise ValueError('Asset is already assigned to different hardware')
    if hardware_id and hardware_id>0:
        assigned=sync.find(ASSETS,**{kind+'_id':hardware_id})
        if assigned and (not asset or assigned['id']!=asset['id']):
            raise ValueError('Installed hardware asset conflicts with observed serial/type')
    return asset


def ensure_asset(sync, kind, type_id, serial, hardware, label):
    asset=asset_candidate(sync,kind,type_id,serial,hardware['id'])
    # Preserve an existing tag. On adoption an observed tag is authoritative only
    # when creating a previously untracked asset; never clear/overwrite it.
    if asset and (hardware.get('asset_tag') or None) not in (None,asset.get('asset_tag')):
        raise ValueError('Hardware and asset tags conflict; review before assignment')
    key={'serial':serial,kind+'_type_id':type_id}
    data={'serial':serial,kind+'_type':type_id,kind:hardware['id']}
    if not asset: data.update(status='used',asset_tag=hardware.get('asset_tag') or None)
    return sync.ensure(ASSETS,key,data,label+' asset')


def retire_module(sync, device_id, bay, module, new_serial=None):
    """Keep physical assets and interface objects; cabled replacement needs review."""
    serial=physical_serial(module.get('serial'))
    interfaces=sync.list('dcim/interfaces/',device_id=device_id,module_id=module['id'])
    cabled=[i['name'] for i in interfaces if i.get('cable')]
    if cabled:
        sync.journal(device_id,bay,serial,new_serial,'refused',cabling='unverified',interfaces=cabled)
        raise ValueError('Cabled module interfaces require explicit cabling review and disconnection before replacement/removal')
    # Refuse cascade loss of other module-owned components; this importer only
    # knows how to preserve interfaces and must not erase nested hardware.
    for endpoint in ('inventory-items','module-bays','power-ports','power-outlets','console-ports','console-server-ports','front-ports','rear-ports'):
        children=sync.list('dcim/'+endpoint+'/',device_id=device_id)
        if any(scalar(c.get('module'))==module['id'] or (c.get('component_type')=='dcim.module' and c.get('component_id')==module['id']) for c in children):
            sync.journal(device_id,bay,serial,new_serial,'refused',cabling='unverified',cascade=endpoint)
            raise ValueError('Module has '+endpoint+'; review cascade before removal')
    ensure_asset(sync,'module',scalar(module['module_type']),serial,module,bay)
    sync.journal(device_id,bay,serial,new_serial,'started',cabling='unverified; no connected cable observed',module_id=module['id'])
    try:
        for interface in interfaces:
            sync.ensure('dcim/interfaces/',{'device_id':device_id,'name':interface['name']},
                        {'module':None},interface['name']+' detached')
        sync.delete('dcim/modules/',module,bay+' installation')
        # Real plugin delete signal returns the assigned asset to stored.
    except Exception:
        sync.journal(device_id,bay,serial,new_serial,'failed',cabling='unverified; inspect partial operation')
        raise
    sync.journal(device_id,bay,serial,new_serial,'removed',cabling='unverified; no cable copied',interfaces=[i['id'] for i in interfaces])
