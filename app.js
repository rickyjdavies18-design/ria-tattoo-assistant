let state={enquiryId:null,answers:{}};

function show(id){
 document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));
 document.getElementById(id).classList.remove('hidden');
 if(id==='dashboard')loadDashboard();
 if(id==='enquiries')loadEnquiries();
 if(id==='customers')loadCustomers();
}

async function loadDashboard(){
 const d=await fetch('/api/dashboard').then(r=>r.json());
 const labels={new_enquiry:'New enquiries',waiting_reference:'Waiting reference',needs_ricky:'Needs Ricky',awaiting_deposit:'Awaiting deposit',confirmed:'Confirmed',completed:'Completed'};
 cards.innerHTML=Object.entries(d.counts).map(([k,v])=>`<div class="stat"><b>${v}</b><span>${labels[k]}</span></div>`).join('');
 today.innerHTML=d.today.length?d.today.map(x=>`<div class="card"><b>${x.start_time} · ${x.full_name||'Customer'}</b><div>${x.session_type} · £${x.total_price}</div></div>`).join(''):'<p class="small">Nothing booked today.</p>';
}

function addBubble(text,who='ria'){chatlog.innerHTML+=`<div class="bubble ${who}">${text}</div>`}
function setControls(html){chatcontrols.innerHTML=html}

async function startTest(){
 state={enquiryId:null,answers:{}};
 chatlog.innerHTML='';
 addBubble("Hi, I’m Ria, Ricky’s assistant. Ricky’s tied up, so I’ll get you to the right place.");
 addBubble("What do you need?");
 setControls(`
 <button class="choice primary" onclick="route('tattoo')">Tattoo enquiry</button>
 <button class="choice" onclick="route('existing')">Existing booking or question</button>
 <button class="choice" onclick="route('personal')">Speak to Ricky personally</button>`);
}

async function route(route){
 const labels={tattoo:'Tattoo enquiry',existing:'Existing booking or question',personal:'Speak to Ricky personally'};
 addBubble(labels[route],'user');
 const res=await fetch('/api/enquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route})}).then(r=>r.json());
 state.enquiryId=res.id;
 if(route==='personal'){
   addBubble("No problem. I’ll stop here and flag this for Ricky personally.");
   setControls('<button onclick="startTest()">Start again</button>'); return;
 }
 if(route==='existing'){
   addBubble("Got it. I’ll flag this for Ricky so your existing booking can be checked.");
   setControls('<button onclick="startTest()">Start again</button>'); return;
 }
 askTattooType();
}

function askTattooType(){
 addBubble("Is this a new tattoo, cover-up, rework, or something else?");
 setControls(`
 <button class="choice" onclick="answerType('New tattoo')">New tattoo</button>
 <button class="choice" onclick="answerType('Cover-up')">Cover-up</button>
 <button class="choice" onclick="answerType('Rework')">Rework</button>
 <button class="choice" onclick="answerType('Other')">Other</button>`);
}
function answerType(v){addBubble(v,'user');state.answers.tattoo_type=v;askText('idea',"Tell me the tattoo idea.");}
function askText(key,q){addBubble(q);setControls(`<textarea id="ans" rows="3"></textarea><button class="primary" onclick="submitText('${key}')">Continue</button>`)}
async function submitText(key){
 const v=ans.value.trim(); if(!v)return;
 addBubble(v,'user');state.answers[key]=v;
 await fetch(`/api/enquiries/${state.enquiryId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({[key]:v})});
 const flow={idea:['placement','Where on the body?'],placement:['rough_size','Roughly what size?'],rough_size:['style_pref','Black & grey, colour, or not sure?'],style_pref:['reference_notes','Any reference images or notes?'],reference_notes:['preferred_timing','Any preferred date or time of year?']};
 if(flow[key])askText(flow[key][0],flow[key][1]);else saveTattoo();
}
async function saveTattoo(){
 addBubble("Perfect. If you want to book, I’ll show you actual available dates. I’ll only ask for your full details once you choose one.");
 const dates=await fetch('/api/availability?preferred='+encodeURIComponent(state.answers.preferred_date||'')).then(r=>r.json());
 setControls(dates.slice(0,8).map(d=>`<button class="choice" onclick='chooseDate(${JSON.stringify(d)})'>${d.label} · ${d.session_type} · £${d.price}</button>`).join('')+'<button onclick="startTest()">Cancel</button>');
}
function chooseDate(d){
 state.date=d;addBubble(`${d.label} · ${d.session_type} · £${d.price}`,'user');
 addBubble(`Deposit is £50. Remaining balance is £${d.balance} on the day by cash or bank transfer. The session starts at 10:00 AM and runs until the booked piece/session is done.`);
 setControls(`<input id="name" placeholder="Full name"><input id="phone" placeholder="Phone"><input id="email" placeholder="Email"><input id="ig" placeholder="Instagram handle (optional)"><button class="primary" onclick="bookNow()">Create provisional booking</button>`);
}
async function bookNow(){
 const body={enquiry_id:state.enquiryId,appointment_date:state.date.date,full_name:name.value,phone:phone.value,email:email.value,instagram:ig.value};
 const r=await fetch('/api/bookings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const x=await r.json(); if(!r.ok){addBubble(x.error);return}
 state.bookingId=x.booking_id;addBubble("Booked provisionally. £50 deposit is now due. This demo does not take real payment.");
 setControls('<button class="primary" onclick="markPaid()">Simulate £50 deposit paid</button><button onclick="startTest()">Start again</button>');
}
async function markPaid(){
 await fetch(`/api/bookings/${state.bookingId}/mark-deposit-paid`,{method:'POST'});
 addBubble("Deposit marked paid. Booking confirmed ✅");
 setControls('<button onclick="startTest()">Start another test</button>');loadDashboard();
}

async function loadEnquiries(){
 const xs=await fetch('/api/enquiries').then(r=>r.json());
 enquiryList.innerHTML=xs.map(x=>`<div class="card"><b>#${x.id} · ${x.route}</b><div>${x.status}</div><div class="small">${x.full_name||'No booking details yet'} ${x.instagram?('· @'+x.instagram.replace('@','')):''}</div>
 <div class="row"><button onclick="setStatus(${x.id},'needs_ricky')">Needs Ricky</button><button onclick="setStatus(${x.id},'waiting_reference')">Waiting reference</button><button onclick="setStatus(${x.id},'completed')">Completed</button></div></div>`).join('');
}
async function setStatus(id,status){
 await fetch(`/api/enquiries/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});loadEnquiries();
}
async function loadCustomers(){
 const q=custSearch.value||'';
 const xs=await fetch('/api/customers?q='+encodeURIComponent(q)).then(r=>r.json());
 customerList.innerHTML=xs.map(c=>`<div class="card"><b>${c.full_name}</b><div>${c.phone}</div><div>${c.email}</div><div>${c.instagram||''}</div></div>`).join('');
}
startTest();loadDashboard();
