(() => {
  'use strict';
  const menu = document.querySelector('.mobile-menu');
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu?.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
  document.addEventListener('click', event => {
    if (menu?.open && !menu.contains(event.target)) menu.open = false;
  });
  const storage = {get(k, fallback=null){try{return JSON.parse(localStorage.getItem(k)) ?? fallback;}catch(_){return fallback;}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true;}catch(_){return false;}}};
  let user = document.body.dataset.userId || storage.get('fgk.activeUser');
  let status = document.getElementById('connection-status');
  const queueKey = () => 'fgk.outbox.' + user;
  function show(text, danger=false){if(!status)return;status.hidden=false;status.className='notice '+(danger?'warning':'');status.textContent=text;}
  function count(){return storage.get(queueKey(),[]).length;}
  function announce(){if(!navigator.onLine)show('Offline. Updates stay on this device until synchronization succeeds. '+count()+' update(s) waiting.');else if(count())show(count()+' update(s) waiting to synchronize.');}
  async function session(){const response=await fetch('/accounts/api/session/',{credentials:'same-origin',headers:{'Accept':'application/json'}});if(!response.ok || !response.headers.get('content-type')?.includes('application/json'))throw Error('Sign in to synchronize saved updates.');return response.json();}
  let syncing=false;
  async function sync(){
    if(!navigator.onLine || !user || syncing || !count())return;
    syncing=true;
    renderOutbox();
    try {
      const current=await session();
      if(current.user!==user)throw Error('Sign in to the account that created these updates.');
      for(const item of storage.get(queueKey(),[])) {
        const response=await fetch('/accounts/api/offline/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':current.csrf},body:JSON.stringify(item)});
        const result=response.headers.get('content-type')?.includes('application/json') ? await response.json() : {};
        // Re-read after each response so a newly captured lead cannot be overwritten.
        const pending=storage.get(queueKey(),[]);
        if(!response.ok) {
          const saved=pending.find(entry=>entry.id===item.id);
          if(saved)saved.error=result.error||'Sign in or ask the office to review this update.';
          if(!storage.set(queueKey(),pending))throw Error('Device storage could not be updated. Keep this page open.');
          show('An update needs review. Its details remain in the device outbox below.',true);
          return;
        }
        if(!storage.set(queueKey(),pending.filter(entry=>entry.id!==item.id)))throw Error('The server saved an update but device storage could not be updated. Retrying is safe.');
      }
      show(count() ? count()+' update(s) still waiting. Use Retry synchronization.' : 'All queued updates are saved to the server.');
    }catch(error){show(error.message||'Unable to sync. Your updates remain on this device.',true);}
    finally{syncing=false;renderOutbox();}
  }
  function renderOutbox(){
    if(!status)return;
    let panel=document.getElementById('device-outbox');
    const queue=storage.get(queueKey(),[]);
    if(!queue.length){panel?.remove();return;}
    if(!panel){panel=document.createElement('section');panel.id='device-outbox';panel.className='panel';status.after(panel);}
    panel.replaceChildren();
    const heading=document.createElement('h2');heading.textContent='Device outbox';panel.append(heading);
    const description=document.createElement('p');description.textContent='These updates are waiting for server confirmation. Review details before discarding anything.';panel.append(description);
    const retry=document.createElement('button');retry.type='button';retry.className='button secondary';retry.textContent=syncing?'Synchronizing…':'Retry synchronization';retry.disabled=syncing;retry.onclick=sync;panel.append(retry);
    for(const item of queue){
      const details=document.createElement('details');details.className='spacer';
      const summary=document.createElement('summary');summary.textContent=(item.kind==='lead'?'Lead: '+(item.data.name||item.data.address||'New conversation'):'Job update: '+(item.data.status||'Status'))+(item.error?' — needs review':'');details.append(summary);
      if(item.error){const error=document.createElement('p');error.className='notice warning';error.textContent=item.error;details.append(error);}
      const fields=document.createElement('dl');fields.className='definition-list';
      const labels={name:'Name',address:'Address',email:'Email',phone:'Phone',kind:'Property type',outcome:'Outcome',message:'Notes',notes:'Notes',status:'Job status',checklist:'Checklist',follow_up_at:'Follow-up'};
      for(const [key,label] of Object.entries(labels)){if(!item.data[key])continue;const row=document.createElement('div'),term=document.createElement('dt'),value=document.createElement('dd');term.textContent=label;value.textContent=Array.isArray(item.data[key])?item.data[key].join(', '):item.data[key];row.append(term,value);fields.append(row);}details.append(fields);
      const discard=document.createElement('button');discard.type='button';discard.className='button danger spacer';discard.disabled=syncing;discard.textContent='Discard this update';
      discard.onclick=()=>{if(syncing)return;if(!confirm('Discard this device update? Check the server record first if a previous synchronization may have succeeded.'))return;
        if(!storage.set(queueKey(),storage.get(queueKey(),[]).filter(entry=>entry.id!==item.id))){show('The update could not be removed from device storage.',true);return;}
        renderOutbox();show(count()?count()+' update(s) waiting.':'The device outbox is empty.');};details.append(discard);panel.append(details);
    }
  }
  if(user && document.body.dataset.userId){const previous=storage.get('fgk.activeUser');if(previous&&previous!==user){for(const key of Object.keys(localStorage)){if(key.startsWith('fgk.'))localStorage.removeItem(key);}}storage.set('fgk.activeUser',user);}
  document.querySelectorAll('form[data-offline-kind]').forEach(form=>form.addEventListener('submit',event=>{
    if(navigator.onLine && !document.body.hasAttribute('data-offline-shell'))return;
    event.preventDefault();if(!user){show('Sign in while online before using the offline outbox.',true);return;}
    const fields=new FormData(form);const data=Object.fromEntries(fields.entries());delete data.csrfmiddlewaretoken;
    if(form.dataset.offlineKind==='status'){data.job_id=form.dataset.jobId;data.status=event.submitter?.value;data.checklist=fields.getAll('checklist');}
    const queue=storage.get(queueKey(),[]);if(queue.length>=50){show('The outbox is full. Reconnect to synchronize your updates.',true);return;}
    queue.push({id:crypto.randomUUID(),user,kind:form.dataset.offlineKind,data});
    if(storage.set(queueKey(),queue)){show('Saved to this device only. '+queue.length+' update(s) not yet saved to the server.');form.reset();renderOutbox();if(navigator.onLine)sync();}else show('Device storage is unavailable. This update has not been saved.',true);
  }));
  async function cacheSummary(){try{if(!navigator.onLine||!user)return;const response=await fetch('/accounts/api/summary/',{credentials:'same-origin'});if(response.ok){const data=await response.json();if(data.user===user)storage.set('fgk.summary.'+user,{jobs:data.jobs,savedAt:new Date().toISOString()});}}catch(_){}}
  const list=document.getElementById('offline-assignments');if(list){const saved=storage.get('fgk.summary.'+user);if(saved?.jobs?.length){for(const job of saved.jobs){const p=document.createElement('p');p.textContent=job.number+' · '+new Date(job.start).toLocaleString()+' · '+job.status;list.append(p);}const small=document.createElement('small');small.textContent='Last synced '+new Date(saved.savedAt).toLocaleString();list.append(small);}else list.textContent='No assignment summaries saved on this device.';}
  document.querySelectorAll('[data-logout]').forEach(button=>button.closest('form')?.addEventListener('submit',event=>{if(count()){event.preventDefault();show('Synchronize or review and discard pending updates before signing out.',true);renderOutbox();return;}for(const key of Object.keys(localStorage)){if(key.startsWith('fgk.'))localStorage.removeItem(key);}navigator.serviceWorker?.controller?.postMessage('LOGOUT');}));
  if('serviceWorker' in navigator && (location.protocol==='https:' || ['127.0.0.1','localhost'].includes(location.hostname)))navigator.serviceWorker.register('/crew/sw.js',{scope:'/crew/'}).catch(()=>{});
  document.querySelector('[data-enable-push]')?.addEventListener('click',async()=>{const feedback=document.querySelector('[data-push-status]');try{if(!('PushManager' in window)||!('Notification' in window))throw Error('Push is unavailable here. Use the crew notification center.');const current=await session();if(!current.push.enabled)throw Error('Push is not configured yet.');if(await Notification.requestPermission()!=='granted')throw Error('Notifications were not enabled. Your in-app inbox is still available.');const reg=await navigator.serviceWorker.getRegistration('/crew/');if(!reg)throw Error('Open the crew workspace first, then try again.');const raw=current.push.public_key.replace(/-/g,'+').replace(/_/g,'/');const key=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));const subscription=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:key});const response=await fetch('/accounts/api/push/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':current.csrf},body:JSON.stringify(subscription)});if(!response.ok)throw Error('Subscription could not be saved.');feedback.textContent='Notifications enabled on this device.';}catch(error){feedback.textContent=error.message;}});
  window.addEventListener('online',()=>{show('Connection restored. Checking the outbox.');sync();cacheSummary();});window.addEventListener('offline',announce);announce();renderOutbox();sync();cacheSummary();
})();
