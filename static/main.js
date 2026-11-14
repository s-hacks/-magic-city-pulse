const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let resources=[],state={},category='',matchIds=null,areas=[],map=null,markers=null,selectedZip=null,userLocation=null,userMarker=null,routeLayer=null,activeDestination=null,routeVersion=0,lastMapIds='',locationBusy=false,conversationHistory=[],lastShownIds=[],conversationVersion=0,resourceContext={},requestedTiming={};
async function api(path,body){const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await response.json();if(!response.ok)throw Error(data.error||'Please try again.');return data;}
function tab(provider){$('neighbor').hidden=provider;$('provider').hidden=!provider;for(const [id,active] of [['neighbor-tab',!provider],['provider-tab',provider]]){$(id).classList.toggle('active',active);$(id).setAttribute('aria-selected',active);}if(provider)loadDemand();else{refresh();setTimeout(()=>map?.invalidateSize(),50);}}
$('neighbor-tab').onclick=()=>tab(false);$('provider-tab').onclick=()=>tab(true);
let animateChat=!window.matchMedia('(prefers-reduced-motion: reduce)').matches,followChat=true;
function scrollChat(){if(followChat)$('messages').scrollTop=$('messages').scrollHeight;}
$('messages').addEventListener('scroll',()=>{followChat=$('messages').scrollHeight-$('messages').scrollTop-$('messages').clientHeight<65;$('jump-latest').hidden=followChat;});
$('jump-latest').onclick=()=>{followChat=true;scrollChat();$('jump-latest').hidden=true;};
function syncMotion(){document.body.classList.toggle('motion-reduced',!animateChat);$('motion-toggle').setAttribute('aria-pressed',String(animateChat));$('motion-toggle').textContent=animateChat?'✦ Motion on':'Motion off';}
$('motion-toggle').onclick=()=>{animateChat=!animateChat;syncMotion();};
window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',event=>{animateChat=!event.matches;syncMotion();});syncMotion();
function mood(value){const chat=document.querySelector('.chat');chat.dataset.mood=value;const text={thinking:'Thinking it through…',replying:'A little help is on its way.',ready:'Right here with you.'}[value]||'Right here with you.';$('pip-mood').replaceChildren();const dot=document.createElement('span');dot.className='presence-dot';dot.setAttribute('aria-hidden','true');$('pip-mood').append(dot,document.createTextNode(text));}
function bubble(text,user=false){
 const el=document.createElement('div');el.className='bubble '+(user?'user':'bot');const copy=document.createElement('span');copy.className='reply-copy';copy.textContent=text;el.append(copy);
 conversationHistory.push({role:user?'user':'assistant',content:String(text).slice(0,700)});conversationHistory=conversationHistory.slice(-10);$('messages').append(el);scrollChat();return el;
}
function typingBubble(){
 const el=document.createElement('div');el.className='bubble bot typing-bubble';el.setAttribute('role','status');
 const dots=document.createElement('span');dots.className='typing-dots';dots.setAttribute('aria-hidden','true');
 for(let i=0;i<3;i++){const dot=document.createElement('span');dots.append(dot);}
 const label=document.createElement('span');label.className='typing-label';label.textContent='Pip is thinking';el.append(dots,label);$('messages').append(el);scrollChat();return el;
}
async function revealReply(answer,text){
 if(!animateChat||document.hidden)return;
 const copy=answer.querySelector('.reply-copy');if(!copy)return;
 copy.textContent='';copy.setAttribute('aria-hidden','true');
 // Hold announcements until the visible reply is complete; keep only one text copy.
 answer.setAttribute('aria-busy','true');
 const skip=document.createElement('button');skip.className='reveal-skip';skip.textContent='Show all';let finish=false;skip.onclick=()=>{finish=true;};answer.append(skip);answer.classList.add('is-revealing');
 const chars=Array.from(text),duration=Math.min(1500,Math.max(250,chars.length*4));
 await new Promise(resolve=>{let started=null;function frame(timestamp){if(started===null)started=timestamp;const progress=Math.min(1,(timestamp-started)/duration);const count=finish||!animateChat||document.hidden?chars.length:Math.floor(progress*chars.length);copy.textContent=chars.slice(0,count).join('');scrollChat();if(count>=chars.length){resolve();return;}requestAnimationFrame(frame);}requestAnimationFrame(frame);});
 copy.textContent=text;copy.removeAttribute('aria-hidden');answer.setAttribute('aria-busy','false');skip.remove();answer.classList.remove('is-revealing');
}

async function send(message){
 if($('send').disabled)return;
 const recentHistory=conversationHistory.slice(-10),previousCategory=state.category;
 followChat=true;conversationVersion++;$('send').disabled=true;mood('thinking');document.querySelectorAll('[data-prompt],.quick-reply').forEach(b=>b.disabled=true);
 bubble(message,true);
 const thinking=typingBubble();const slowHint=setTimeout(()=>{const label=thinking.querySelector('.typing-label');if(label)label.textContent='Still here—this is taking a little longer';},8000);
 try{
  const result=await api('/api/chat',{message,state,history:recentHistory,last_matches:lastShownIds,resource_context:resourceContext,location:userLocation||undefined});
  state=result.state||state;thinking.remove();clearTimeout(slowHint);showLLM(result.llm);mood('replying');const answer=bubble(result.reply);await revealReply(answer,result.reply);
  if(result.intent==='comparison'){
   if(result.map_matches?.length){clearRoute();activeDestination=null;category='';matchIds=result.map_matches.map(r=>r.id);await refresh();$('result-caption').textContent='The food place and shelter we discussed · check hours before going.';const button=document.createElement('button');button.className='view-map';button.textContent='Show both places on the map ↗';button.onclick=()=>{$('nearby').scrollIntoView({behavior:animateChat?'smooth':'auto',block:'start'});};answer.append(document.createElement('br'),button);if(!result.map_matches.some(r=>r.is_demo)){const walk=document.createElement('button');walk.className='view-map';walk.textContent='Walking route between them ↗';walk.onclick=()=>routeBetween(result.comparison.food_id,result.comparison.shelter_id);answer.append(walk);}}
  }else if(result.intent==='conversation'){
   if(result.focus_resource_id){const resource=resources.find(r=>r.id===result.focus_resource_id);if(resource){const button=document.createElement('button');button.className='view-map';button.textContent='See this place & plan my route ↗';button.onclick=()=>chooseDestination(resource.id);answer.append(document.createElement('br'),button);}}
  }else if(result.needs_info){
   if(result.category_changed||(previousCategory&&state.category!==previousCategory)){
    clearRoute();activeDestination=null;lastShownIds=[];matchIds=[];category=state.category||'';render();
    $('result-caption').textContent='Switching to '+({shelter:'shelter',food:'food',health:'healthcare'}[state.category]||'your next request')+' · Pip needs a couple of details first.';
   }
  }else if(Array.isArray(result.matches)){
   clearRoute();activeDestination=null;category='';matchIds=result.matches.map(r=>r.id);lastShownIds=matchIds.slice();requestedTiming=Object.fromEntries(result.matches.map(r=>[r.id,r.requested_time_status]));
   $('result-caption').textContent=result.matches.length?'Pip’s closest matches · confirm your requested time.':'Your request is saved. No eligible matches are listed.';
   await refresh();addSuggestions(answer,result);
  }
  addQuickReplies(answer,result.quick_replies);
 }catch(e){bubble('Hmm, that didn’t work. '+e.message+' You can try again.');}
 finally{clearTimeout(slowHint);thinking.remove();mood('ready');$('send').disabled=false;document.querySelectorAll('[data-prompt],.quick-reply').forEach(b=>b.disabled=false);$('message').focus();}
}
function addQuickReplies(answer,replies){
 if(!Array.isArray(replies)||!replies.length)return;
 const row=document.createElement('div');row.className='quick-replies';
 replies.slice(0,4).forEach(reply=>{const button=document.createElement('button');button.className='quick-reply';button.textContent=reply.label;button.onclick=()=>send(reply.message);row.append(button);});
 answer.append(row);scrollChat();
}

$('message').addEventListener('input',()=>{$('chat-form').classList.toggle('has-text',Boolean($('message').value.trim()));});
$('chat-form').onsubmit=e=>{e.preventDefault();const message=$('message').value.trim();if(message){$('message').value='';$('chat-form').classList.remove('has-text');send(message);}};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>send(b.dataset.prompt));
$('reset').onclick=()=>{if($('send').disabled)return;state={};conversationHistory=[];lastShownIds=[];resourceContext={};requestedTiming={};conversationVersion++;clearRoute();activeDestination=null;matchIds=null;$('messages').replaceChildren();bubble('A fresh start ☀️ What do you need today—a meal, a place to stay, or a clinic?');refresh();};
document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{category=b.dataset.category;matchIds=null;$('result-caption').textContent='Explore your neighborhood’s resources.';render();});
function focusCard(id){const card=document.getElementById('r-'+id);if(card){card.scrollIntoView({behavior:animateChat?'smooth':'auto',block:'center'});card.classList.add('highlight');setTimeout(()=>card.classList.remove('highlight'),1800);}}
function render(){
 const rows=resources.filter(r=>(!category||r.category===category)&&(!matchIds||matchIds.includes(r.id)));
 $('resource-count').textContent=rows.length+(rows.length===1?' PLACE TO EXPLORE':' PLACES TO EXPLORE');
 document.querySelectorAll('[data-category]').forEach(b=>b.classList.toggle('selected',b.dataset.category===category));
 $('cards').innerHTML=rows.length?rows.map((r,i)=>`<article id="r-${esc(r.id)}" class="card resource-card">
 <div class="resource-top"><span class="category">${{food:'🥕 Food & a little comfort',shelter:'🏡 A place to stay',health:'🌷 A little care'}[r.category]}</span><span class="badge ${esc(r.status)}">${r.provider_confirmed?'✓ Drop confirmed':r.status==='open'?'● Open by schedule':r.status==='closed'?'Closed now':'Check hours'}</span></div>
 <h3><span class="place-number">${i+1}</span> ${esc(r.name.replace(' · Demo',''))}</h3><p>${esc(r.neighborhood)} · ${esc(r.zip)}</p><p>${esc(r.address)}</p><p>◷ ${esc(r.hours_today)}</p>${requestedTiming[r.id]==='closed'?'<p class="time-caution">Not open at your requested time</p>':''}
 ${r.category==='food'?`<p>${r.subcategory==='snap_retailer'?'SNAP purchases · not free food':r.bags_available==null?'Bag availability: contact provider':esc(r.bags_available)+' bags listed'+(r.is_demo?' · demo count':'')}</p>`:''}
 ${r.category==='shelter'?`<p>Age ${esc(r.min_age)}+ · ${esc((r.allowed_genders||[]).join(', '))}<br>${esc(r.beds_available??'Unconfirmed')} beds listed · ${esc(r.check_in_window)}</p>`:''}
 ${r.category==='health'?'<p>Sliding-scale care · no insurance welcome</p>':''}
 <details><summary>What to bring & how to get there <span>＋</span></summary><p><b>A little preparation:</b> ${esc(r.what_to_bring)}</p><p class="transit">▱ ${esc(r.nearest_max_stop)}</p>${r.transit_is_approximate?'<p>Approximate corridor. Check the stop before traveling.</p>':''}</details>
 <div class="card-bottom"><span class="demo-note">${r.is_demo?'Demo place · illustrative location':r.availability_is_demo?'Local listing · demo bed counts':'Local listing · confirm availability'}</span><button class="map-link" data-map-id="${esc(r.id)}">${r.is_demo?'Demo pin ↗':'Plan my route ↗'}</button></div></article>`).join(''):'<div class="card empty">A little room to keep looking. Try another neighborhood or tell Pip what would help.</div>';
 document.querySelectorAll('[data-map-id]').forEach(b=>b.onclick=()=>chooseDestination(b.dataset.mapId));renderMap(rows);
}
function showOnMap(id){const r=resources.find(r=>r.id===id);if(!r)return;if(map){map.setView([r.lat,r.lon],15);markers.eachLayer(m=>{if(m.resourceId===id)m.openPopup();});}$('map').scrollIntoView({behavior:animateChat?'smooth':'auto',block:'center'});if(!map){const pin=document.querySelector(`[data-resource="${id}"]`);if(pin){pin.classList.add('highlight');pin.focus();setTimeout(()=>pin.classList.remove('highlight'),1800);}}}
function addSuggestions(answer,result){
 if(!result.matches?.length)return;lastShownIds=result.matches.map(r=>r.id);
 for(const kind of ['food','shelter','health']){const ids=result.matches.filter(r=>r.category===kind).map(r=>r.id);if(ids.length)resourceContext[kind]={ids,selected_id:ids.includes(resourceContext[kind]?.selected_id)?resourceContext[kind].selected_id:null};}
 const box=document.createElement('div');box.className='chat-findings';
 if(result.logged_request){const request=result.logged_request;const context=document.createElement('div');context.className='request-summary';const place=areas.find(a=>a.zip_code===request.zip_code)?.neighborhood||resources.find(r=>r.zip===request.zip_code)?.neighborhood||request.zip_code;const when=new Date(request.date_time).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});context.textContent=({food:'🥕 Food',shelter:'🏡 Shelter',health:'🌷 Healthcare'}[request.category]||request.category)+' · '+place+' · '+when;box.append(context);}
 const title=document.createElement('div');title.className='findings-title';title.textContent=result.presentation?.title||'A few places to start';box.append(title);
 result.matches.forEach((r,i)=>{const button=document.createElement('button');button.className='finding';button.innerHTML=`<span class="finding-icon">${['🥕','🏡','🌷'][['food','shelter','health'].indexOf(r.category)]}</span><span><b>${esc(r.name.replace(' · Demo',''))}</b><small>${esc(r.neighborhood)}${r.is_demo?' · Demo place':''}${r.requested_time_status==='closed'?' · Closed at your requested time':''}</small></span><span class="finding-number">${i+1} ↗</span>`;button.onclick=()=>{matchIds=result.matches.map(r=>r.id);category='';render();chooseDestination(r.id);};box.append(button);});
 const note=document.createElement('p');note.className='findings-note';note.textContent=result.presentation?.note||'Check service details before traveling.';box.append(note);
 const view=document.createElement('button');view.className='view-map';view.textContent='♡ '+(result.presentation?.map_label||'See your options on the map');view.onclick=()=>{matchIds=result.matches.map(r=>r.id);category='';render();$('nearby').scrollIntoView({behavior:animateChat?'smooth':'auto',block:'start'});};box.append(view);if(!userLocation){const consent=document.createElement('div');consent.className='location-invite';const text=document.createElement('p');text.textContent='Want me to find the closest local place and help you get there?';const allow=document.createElement('button');allow.className='location-button';allow.textContent='◎ Yes, use my location';allow.onclick=()=>useLocation();const skip=document.createElement('button');skip.className='text-choice';skip.textContent='Keep using my ZIP';skip.onclick=()=>{consent.replaceChildren();const note=document.createElement('p');note.textContent='Of course. We’ll stick with your ZIP. No need to share your location.';consent.append(note);};const privacy=document.createElement('small');privacy.textContent='Only after you choose. Coordinates go to our routing service to plan your route; they aren’t saved in your request.';consent.append(text,allow,skip,privacy);box.append(consent);}answer.append(box);scrollChat();
}

async function refresh(){try{resources=await api('/api/resources');render();}catch(e){$('cards').innerHTML='<div class="card empty">Could not load resources. Check that python3 app.py is running.</div>';}}
function renderMap(rows){
 if(map){
  markers.clearLayers();
  rows.forEach((r,i)=>{const label=document.createElement('div');const title=document.createElement('b');title.textContent=r.name;const detail=document.createElement('p');detail.textContent=r.is_demo?'Illustrative demo pin · not a real pickup destination':r.address;const button=document.createElement('button');button.className='location-button';button.textContent=r.is_demo?'See demo details':'Walk here';button.onclick=()=>r.is_demo?focusCard(r.id):chooseDestination(r.id);label.append(title,detail,button);
   const marker=L.marker([r.lat,r.lon],{icon:L.divIcon({className:'place-pin '+r.category,html:`<span>${i+1}</span>`,iconSize:[36,43],iconAnchor:[18,43],popupAnchor:[0,-40]})}).bindPopup(label).addTo(markers);marker.resourceId=r.id;
  });
  const ids=rows.map(r=>r.id).join(',');
  if(ids!==lastMapIds&&!routeLayer&&rows.length){const bounds=L.latLngBounds(rows.map(r=>[r.lat,r.lon]));if(userLocation)bounds.extend([userLocation.lat,userLocation.lon]);map.fitBounds(bounds,{padding:[65,65],maxZoom:14});}lastMapIds=ids;
  return;
 }
 const pins=$('offline-pins');if(!pins)return;
 pins.innerHTML=rows.map((r,i)=>`<button class="pin" style="left:${Math.max(5,Math.min(92,(r.lon+86.915)/.19*90))}%;top:${Math.max(20,Math.min(78,80-(r.lat-33.48)/.075*60))}%" data-resource="${esc(r.id)}" title="${esc(r.name)}" aria-label="${esc(r.name)}">${i+1}</button>`).join('');document.querySelectorAll('[data-resource]').forEach(b=>b.onclick=()=>focusCard(b.dataset.resource));
}
function setupLeaflet(){
 if(!window.L||map)return;const el=$('map');const fallback=el.innerHTML;
 try{el.innerHTML='';map=L.map(el,{scrollWheelZoom:false}).setView([33.516,-86.83],12);L.control.scale({imperial:true}).addTo(map);markers=L.layerGroup().addTo(map);
  const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19}).addTo(map);
  let loaded=0,errors=0;
  tiles.on('tileload',()=>{loaded++;$('map-status').textContent='Birmingham street map · select a numbered place to plan your way there.';});
  tiles.on('tileerror',()=>{errors++;if(!loaded&&errors>=3)$('map-status').textContent='Street tiles are unavailable right now. Your pins remain visible; try opening directions below.';});
  render();if(userLocation)drawUserLocation();
 }catch{if(map){try{map.remove();}catch{}}map=null;el.innerHTML=fallback;$('map-status').textContent='Street map unavailable. This is an offline overview; use the directions link for navigation.';render();}
}
async function loadLeaflet(){
 const sources=[['/static/vendor/leaflet.js','/static/vendor/leaflet.css'],['https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css'],['https://unpkg.com/leaflet@1.9.4/dist/leaflet.js','https://unpkg.com/leaflet@1.9.4/dist/leaflet.css']];
 for(const [src,css] of sources){
  try{await new Promise((resolve,reject)=>{const tag=document.createElement('script');tag.src=src;const timer=setTimeout(()=>{tag.remove();reject(Error('Map load timed out'));},7000);tag.onload=()=>{clearTimeout(timer);resolve();};tag.onerror=()=>{clearTimeout(timer);tag.remove();reject(Error('Map unavailable'));};document.head.append(tag);});
   const style=document.createElement('link');style.rel='stylesheet';style.href=css;style.onload=()=>map?.invalidateSize();document.head.append(style);setupLeaflet();return;
  }catch{}
 }
 $('map-status').textContent='You’re seeing the offline overview because the street map could not load. Directions can still open in Google Maps.';
}
function drawUserLocation(){if(!map||!userLocation)return;if(userMarker)map.removeLayer(userMarker);userMarker=L.circleMarker([userLocation.lat,userLocation.lon],{radius:10,color:'#fff',weight:3,fillColor:'#427cba',fillOpacity:1}).bindTooltip('You are here').addTo(map);}
async function useLocation(){
 if(locationBusy)return;if(!navigator.geolocation){$('location-status').textContent='This browser cannot share location. You can keep using your ZIP.';return;}
 const locationTurn=conversationVersion;
 locationBusy=true;$('use-location').disabled=true;$('location-status').textContent='Your browser will ask for permission. Choose Allow to share your current position.';
 try{
  const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:30000}));
  if(locationTurn!==conversationVersion){$('location-status').textContent='Your request changed while location was loading. Tap Use my location again for your current request.';return;}
  const {latitude:lat,longitude:lon,accuracy}=position.coords;
  if(lat<=33.3||lat>=33.75||lon<=-87.1||lon>=-86.5)throw Error('Your location is outside the Birmingham area. We can keep using your ZIP.');
  userLocation={lat,lon};$('clear-location').hidden=false;const chosenDestination=activeDestination;clearRoute();drawUserLocation();
  $('location-status').textContent=`Location shared for this page only${accuracy>500?' · approximate device position':''}. Finding nearby local places…`;
  if(chosenDestination){$('location-status').textContent='Location shared for this page only. Planning your walk to the place you chose.';await buildRoute(chosenDestination);return;}
  if(state.category){
   const result=await api('/api/resources/nearby',{location:userLocation,state:{category:state.category,food_preference:state.food_preference,age:state.age,gender:state.gender}});
   if(locationTurn!==conversationVersion)return;
   matchIds=result.matches.map(r=>r.id);category='';await refresh();
   const answer=bubble(result.matches.length?'Thank you, neighbor! I’ve refreshed your options using your location. These are local listings—please confirm they can help at your requested time.':'I couldn’t find a local match for those needs. We can keep looking by ZIP.');
   if(result.matches.length){addSuggestions(answer,{matches:result.matches,presentation:{title:'Closer to you',note:'Local listings; services and hours aren’t live-confirmed.',map_label:'See my nearby places'}});activeDestination=result.matches[0].id;await buildRoute(activeDestination);}
  }else{$('location-status').textContent='Location shared for this page. Ask Pip for food, shelter, or a clinic, then choose a place to plan your route.';map?.setView([lat,lon],14);}
 }catch(error){const explanations={1:'No worries—location permission was declined. We’ll keep using your ZIP.',2:'Your device couldn’t find a location. Try again or keep using your ZIP.',3:'Location took too long. Try again or keep using your ZIP.'};$('location-status').textContent=explanations[error.code]||error.message||'Location unavailable. Keep using your ZIP.';}
 finally{locationBusy=false;$('use-location').disabled=false;}
}
function clearRoute(){routeVersion++;if(routeLayer&&map)map.removeLayer(routeLayer);routeLayer=null;$('journey').hidden=true;}
function forgetLocation(){clearRoute();if(userMarker&&map)map.removeLayer(userMarker);userMarker=null;userLocation=null;activeDestination=null;$('clear-location').hidden=true;$('location-status').textContent='Location cleared from this page. We’ll keep using your ZIP.';render();}
function directionsURL(resource,mode){const params=new URLSearchParams({api:'1',destination:`${resource.lat},${resource.lon}`,travelmode:mode});if(userLocation)params.set('origin',`${userLocation.lat},${userLocation.lon}`);return 'https://www.google.com/maps/dir/?'+params;}
function journeyPanel(resource){
 const panel=$('journey');panel.hidden=false;
 panel.innerHTML=`<div class="journey-title"><div><span class="eyebrow">YOUR NEXT LITTLE STEP</span><h3>${esc(resource.name)}</h3><p>${esc(resource.address)}</p></div><button id="close-journey" class="text-btn" aria-label="Close route">×</button></div><div class="journey-modes"><button id="walk-mode" class="selected">🚶 Walking route</button><button id="transit-mode">▱ MAX / transit</button></div><p id="route-message" role="status"></p><div id="route-details"></div><div class="route-actions"><a class="location-button" id="external-directions" target="_blank" rel="noopener noreferrer">Open walking directions ↗</a><button id="forget-location" class="text-choice">Clear my location</button></div>`;
 $('close-journey').onclick=clearRoute;$('walk-mode').onclick=()=>buildRoute(resource.id);$('transit-mode').onclick=()=>showTransit(resource);$('forget-location').onclick=forgetLocation;$('external-directions').href=directionsURL(resource,'walking');
}
function showTransit(resource){
 clearRoute();journeyPanel(resource);$('walk-mode').classList.remove('selected');$('transit-mode').classList.add('selected');$('route-message').textContent='Listed MAX connection: '+resource.nearest_max_stop;
 $('route-details').textContent=(resource.transit_is_approximate?'This corridor is approximate. ':'')+'Open Google Maps to check current transit directions and schedules. Bus fares may apply; this app does not issue passes.';$('external-directions').textContent='Check transit in Google Maps ↗';$('external-directions').href=directionsURL(resource,'transit');
}
async function chooseDestination(id){
 const resource=resources.find(r=>r.id===id);if(!resource)return;
 if(resourceContext[resource.category])resourceContext[resource.category].selected_id=id;
 if(resource.is_demo){showOnMap(id);$('location-status').textContent='This is a demo pin, not a verified pickup destination. Use your location to find nearby local listings for real directions.';return;}
 activeDestination=id;showOnMap(id);
 if(!userLocation){journeyPanel(resource);$('route-message').textContent='Can Pip use your location to plan a walking route? Tap “Use my location” above. You can also enter your starting point in Google Maps.';$('route-details').textContent='Coordinates will be sent to the pedestrian routing service only after you choose to share.';return;}
 await buildRoute(id);
}
async function buildRoute(id){
 const resource=resources.find(r=>r.id===id);if(!resource||resource.is_demo)return;
 if(!userLocation){await chooseDestination(id);return;}
 clearRoute();activeDestination=id;const version=routeVersion;journeyPanel(resource);$('route-message').textContent='Finding a walking path through the neighborhood…';$('map').scrollIntoView({behavior:animateChat?'smooth':'auto',block:'center'});
 try{
  const result=await api('/api/route',{location:userLocation,resource_id:id});if(version!==routeVersion)return;
  $('route-message').textContent=result.message;
  if(result.available){
   if(map){routeLayer=L.geoJSON(result.geometry,{style:{color:'#cc7958',weight:6,opacity:.9,lineCap:'round'}}).addTo(map);map.fitBounds(routeLayer.getBounds(),{padding:[55,55],maxZoom:16});drawUserLocation();}
   const minutes=Math.max(1,Math.round(result.duration_s/60));const miles=(result.distance_m/1609.344).toFixed(1);
   $('route-details').innerHTML=`<div class="route-estimate"><strong>${minutes} min walk</strong><span>${miles} miles · estimate${map?'':' · map unavailable'}</span></div><p>Bring: ${esc(resource.what_to_bring)}</p><small>${esc(result.attribution)}</small>`;
  }
 }catch(error){if(version===routeVersion)$('route-message').textContent='We couldn’t load a walking route. Open directions below to keep going.';}
}
$('use-location').onclick=useLocation;
$('clear-location').onclick=forgetLocation;
loadLeaflet();

function recommend(){const area=areas.find(a=>a.zip_code===$('target-zip').value);if(!area)return;selectedZip=area.zip_code;const bags=Number($('bags').value)||0;$('recommendation').innerHTML=`<strong>${area.count} neighbors in ${esc(area.zip_code)} (${esc(area.neighborhood)})</strong> have pending food requests.<br>${area.bags_committed} bags committed today · ${area.uncovered} requests still uncovered.<br>Your ${bags} bags could cover up to ${Math.min(bags,area.uncovered)} requests.<br>Proposed drop site: <b>${esc(area.hosts[0])}</b>`;$('drop-location').value=area.hosts[0]+' · '+area.zip_code;document.querySelectorAll('.heat-cell').forEach(b=>b.classList.toggle('selected',b.dataset.zip===selectedZip));}
async function loadDemand(){try{const d=await api('/api/provider/demand');areas=d.areas;$('pending-count').textContent=d.total_pending;if(!$('base-zip').options.length)$('base-zip').innerHTML=areas.map(a=>`<option value="${a.zip_code}">${a.zip_code} · ${esc(a.neighborhood)}</option>`).join('');const previous=selectedZip;$('target-zip').innerHTML=areas.map(a=>`<option value="${a.zip_code}">${a.zip_code} · ${esc(a.neighborhood)}</option>`).join('');if(previous)$('target-zip').value=previous;$('heatmap').innerHTML=areas.map(a=>`<button type="button" class="heat-cell" data-zip="${a.zip_code}" style="background:${a.count>=9?'#e7a480':a.count>=5?'#edc38d':a.count?'#f2dfb4':'#e5ebdf'}"><span>${esc(a.neighborhood)} · ${a.zip_code}</span><strong>${a.count}</strong><span>pending requests · ${a.bags_committed} bags pledged</span></button>`).join('');document.querySelectorAll('.heat-cell').forEach(b=>b.onclick=()=>{$('target-zip').value=b.dataset.zip;recommend();});$('deployments').innerHTML=d.deployments.length?d.deployments.slice().reverse().map(x=>`<div class="deployment"><b>${esc(x.provider_name)}</b> committed <b>${x.bags_committed} bags</b> to ${esc(x.target_zip)}<br>${esc(x.drop_location)}<br><span class="demo-note">Demo dispatch · ${esc(new Date(x.confirmed_at).toLocaleString())}</span></div>`).join(''):'<div class="empty">Your first food drop could start something good. Confirm a plan to see it here.</div>';recommend();}catch(e){$('confirm-status').textContent=e.message;}}
$('target-zip').onchange=recommend;$('bags').oninput=recommend;
$('provider-form').onsubmit=async e=>{e.preventDefault();$('confirm').disabled=true;try{const result=await api('/api/provider/confirm',{provider_name:$('organization').value.trim(),base_zip:$('base-zip').value,bags_count:Number($('bags').value),target_zip:$('target-zip').value,drop_location:$('drop-location').value.trim()});$('confirm-status').textContent='✓ '+result.deployment.bags_committed+' bags published to the neighbor board. No external notifications were sent.';matchIds=null;category='';await Promise.all([loadDemand(),refresh()]);}catch(e){$('confirm-status').textContent=e.message;}finally{$('confirm').disabled=false;}};
refresh();setInterval(()=>{if(!$('neighbor').hidden)refresh();},10000);

function showLLM(info){
 const reasons={invalid_request:'provider rejected the request',model_unavailable:'model unavailable',missing_key:'server has no API key',invalid_key:'key rejected',access_denied:'provider denied access',request_signature_blocked:'provider blocked the HTTP client signature',rate_limited:'rate limit reached',timeout:'provider timed out',network_error:'network connection failed',invalid_response:'provider returned an unreadable response',provider_http_error:'provider HTTP error',provider_error:'provider request failed'};
 const calls=info?.calls||[];
 if(calls.length){const successes=calls.filter(c=>c.success).length;const failed=calls.find(c=>!c.success);$('llm-status').textContent=successes?`${info.provider} replied · ${successes}/${calls.length} calls succeeded${failed?' · partial fallback: '+(reasons[failed.reason]||failed.reason):''}`:`Offline fallback · ${reasons[failed?.reason]||'no successful LLM call'}`;}
}
api('/api/status').then(s=>{$('llm-status').textContent=s.message;}).catch(()=>{$('llm-status').textContent='Connection status unavailable. Restart the app to load the latest changes.';});

async function routeBetween(foodId,shelterId){
 const food=resources.find(r=>r.id===foodId),shelter=resources.find(r=>r.id===shelterId);
 if(!food||!shelter||food.is_demo||shelter.is_demo)return;
 clearRoute();const version=routeVersion;category='';matchIds=[foodId,shelterId];render();journeyPanel(shelter);
 $('journey').querySelector('h3').textContent='From the food place to the shelter';
 $('walk-mode').onclick=()=>routeBetween(foodId,shelterId);$('transit-mode').hidden=true;
 const url=new URL(directionsURL(shelter,'walking'));url.searchParams.set('origin',`${food.lat},${food.lon}`);$('external-directions').href=url.toString();
 $('route-message').textContent='Checking the walking route between these two places…';$('map').scrollIntoView({behavior:animateChat?'smooth':'auto',block:'center'});
 try{const result=await api('/api/route',{location:{lat:food.lat,lon:food.lon},resource_id:shelterId});if(version!==routeVersion)return;$('route-message').textContent=result.message;
  if(result.available){if(map){routeLayer=L.geoJSON(result.geometry,{style:{color:'#cc7958',weight:6,opacity:.9}}).addTo(map);map.fitBounds(routeLayer.getBounds(),{padding:[55,55],maxZoom:16});}
   $('route-details').textContent=`About ${Math.max(1,Math.round(result.duration_s/60))} minutes walking · ${(result.distance_m/1609.344).toFixed(1)} miles. This does not confirm meals or a bed. Check both places before you go.`;
  }
 }catch{if(version===routeVersion)$('route-message').textContent='The route could not load. You can open walking directions below.';}
}
