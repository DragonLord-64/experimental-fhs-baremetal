#!/usr/bin/env python3
"""Create VM-only retained storage and fresh secrets without printing secret data."""
import base64,json,secrets,subprocess,uuid
K=['minikube','-p','fhs-test','kubectl','--','--context=fhs-test','--request-timeout=30s']
def k(*args, data=None, quiet=False):
 return subprocess.run(K+list(args),input=data,text=True,check=True,stdout=subprocess.DEVNULL if quiet else None)
def apply(obj): k('apply','-f','-',data=json.dumps(obj),quiet=True)
apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'fhs-platform'}})
apply({'apiVersion':'storage.k8s.io/v1','kind':'StorageClass','metadata':{'name':'fhs-retain'},'provisioner':'kubernetes.io/no-provisioner','volumeBindingMode':'WaitForFirstConsumer','reclaimPolicy':'Retain'})
# Retain deliberately avoids the minikube provisioner's changing restart identity.
# Files live inside only the fhs-test node. No automatic delete/reclaim operation.
for i in range(12):
 apply({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':f'fhs-platform-{i}','labels':{'app.kubernetes.io/part-of':'fhs-platform'}},'spec':{'capacity':{'storage':'8Gi'},'accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'fhs-retain','hostPath':{'path':f'/data/fhs-platform/{i}','type':'DirectoryOrCreate'},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['fhs-test']}]}]}}}})
# hostPath does not implement fsGroup ownership. Prepare the dedicated lab paths only.
permissions_pod='fhs-storage-permissions-'+uuid.uuid4().hex[:12]
try:
 k('run',permissions_pod,'-n','fhs-platform','--image=busybox:1.37.0','--restart=Never','--labels=app.kubernetes.io/part-of=fhs-platform','--overrides='+json.dumps({'spec':{'containers':[{'name':'fhs-storage-permissions','image':'busybox:1.37.0','command':['sh','-ec','for n in $(seq 0 11); do mkdir -p /data/$n; chmod 1777 /data/$n; done'],'volumeMounts':[{'name':'data','mountPath':'/data'}]}],'volumes':[{'name':'data','hostPath':{'path':'/data/fhs-platform','type':'DirectoryOrCreate'}}]}}),quiet=True)
 k('-n','fhs-platform','wait','--for=jsonpath={.status.phase}=Succeeded','pod/'+permissions_pod,'--timeout=120s',quiet=True)
finally:
 subprocess.run(K+['-n','fhs-platform','delete','pod',permissions_pod,'--ignore-not-found=true','--wait=true','--timeout=30s'],stdout=subprocess.DEVNULL,check=False)
def secret(name,values):
 exists=subprocess.run(K+['-n','fhs-platform','get','secret',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
 if not exists:
  obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':'fhs-platform'},'type':'Opaque','data':{k:base64.b64encode(v.encode()).decode() for k,v in values.items()}}
  k('create','-f','-',data=json.dumps(obj),quiet=True)
def rand(): return secrets.token_hex(32)
secret('netbox-config',{'secret_key':rand(),'api_token_peppers':'{}','email_password':''})
secret('netbox-superuser',{'username':'admin','password':rand(),'email':'admin@example.invalid','api_token':secrets.token_hex(20)})
secret('netbox-database',{'password':rand(),'postgres-password':rand()})
secret('netbox-valkey',{'valkey-password':rand()})
secret('elastic-credentials',{k:rand() for k in ['elastic-password','kibana-password','filebeat-password','kibana-encryption-key']})
secret('monitoring-grafana-admin',{'admin-user':'admin','admin-password':rand()})
print('Prepared retained lab storage and secrets (existing secrets retained)')
