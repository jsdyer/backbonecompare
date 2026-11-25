export function asn(value) { const s=String(value).trim().replace(/^AS/i,''); if(!/^\d{1,10}$/.test(s))throw new Error('Enter an ASN such as AS852 or 13335.');const n=Number(s);if(!Number.isSafeInteger(n)||n<1||n>4294967294)throw new Error('ASN must be between 1 and 4,294,967,294.');return n; }
const bounded = (value,max=500) => typeof value==='string'?value.slice(0,max):'';
export const validDate = value => typeof value==='string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value));
const utc = value => validDate(value)?(/[Zz]|[+-]\d\d:\d\d$/.test(value)?value:value+'Z'):null;
const count = value => value===null||value===undefined?null:(typeof value==='number'&&Number.isFinite(value)&&value>=0?value:(()=>{throw new Error('Invalid observation count.');})());
export function bgp(body,number,checked) {
  const data=body?.data;if(body?.status!=='ok'||!data||asn(data.resource)!==number||!Array.isArray(data.neighbours)||data.neighbours.length>100000)throw new Error('RIPEstat returned incomplete or mismatched evidence.');
  const neighbours=data.neighbours.map(row=>{if(!['left','right','uncertain'].includes(row.type))throw new Error('Unknown BGP observation type.');return {asn:asn(row.asn),type:row.type,v4:count(row.v4_peers),v6:count(row.v6_peers)};});
  if(!validDate(checked))throw new Error('Missing source check date.');
  return {ok:true,checked_at:checked,observed_at:utc(data.query_starttime),observed_until:utc(data.query_endtime),neighbours};
}
export function directory(body,number,checked) {
  if(!Array.isArray(body?.data)||body.data.length>1||!validDate(checked))throw new Error('PeeringDB returned incomplete evidence.');
  if(!body.data.length)return {ok:true,checked_at:checked,listed:false,name:'',net_id:null,updated_at:null,exchanges:[],facilities:[]};
  const net=body.data[0];if(asn(net.asn)!==number||!Number.isSafeInteger(net.id)||net.id<1)throw new Error('PeeringDB returned a different network.');
  if(!Array.isArray(net.netixlan_set)||!Array.isArray(net.netfac_set)||net.netixlan_set.length>10000||net.netfac_set.length>10000)throw new Error('PeeringDB membership lists are missing.');
  const id=value=>{if(!Number.isSafeInteger(value)||value<1)throw new Error('Invalid membership identifier.');return value;};
  const exchanges=net.netixlan_set.filter(r=>r.status==='ok').map(r=>({id:id(r.ix_id),lan_id:id(r.ixlan_id),name:bounded(r.name),ipv4:!!r.ipaddr4,ipv6:!!r.ipaddr6,updated_at:utc(r.updated)}));
  const facilities=net.netfac_set.filter(r=>r.status==='ok').map(r=>({id:id(r.fac_id),name:bounded(r.name),city:bounded(r.city,150),country:bounded(r.country,3),updated_at:utc(r.updated)}));
  return {ok:true,checked_at:checked,listed:true,name:bounded(net.name),net_id:net.id,updated_at:utc(net.updated),exchanges,facilities};
}
export function fromCapture(raw) { const n=asn(raw.asn);return {asn:n,bgp:bgp(raw.ripe,n,raw.checked_at),directory:directory(raw.peering,n,raw.checked_at)}; }
export function observed(network,family='any',uncertain=false) {
  if(!network.bgp?.ok)return null;const result=new Map();
  for(const row of network.bgp.neighbours){if(row.type==='uncertain'&&!uncertain)continue;if(family==='v4'&&!(row.v4>0))continue;if(family==='v6'&&!(row.v6>0))continue;const item=result.get(row.asn)||{id:row.asn,name:`AS${row.asn}`,types:[],ipv4:false,ipv6:false};if(!item.types.includes(row.type))item.types.push(row.type);item.ipv4 ||= row.v4>0;item.ipv6 ||= row.v6>0;result.set(row.asn,item);}
  return result;
}
export function locations(network,kind,family='any') {
  if(!network.directory?.ok)return null;const result=new Map();
  for(const row of network.directory[kind]){if(kind==='exchanges'&&family==='v4'&&!row.ipv4)continue;if(kind==='exchanges'&&family==='v6'&&!row.ipv6)continue;const prior=result.get(row.id);result.set(row.id,{...row,ipv4:row.ipv4||prior?.ipv4||false,ipv6:row.ipv6||prior?.ipv6||false});}return result;
}
export function overlap(a,b) { if(!a||!b)return {available:false,shared:[],left:[],right:[],countA:null,countB:null};return {available:true,shared:[...a.keys()].filter(id=>b.has(id)).map(id=>({id,a:a.get(id),b:b.get(id)})),left:[...a.keys()].filter(id=>!b.has(id)).map(id=>({id,a:a.get(id)})),right:[...b.keys()].filter(id=>!a.has(id)).map(id=>({id,b:b.get(id)})),countA:a.size,countB:b.size}; }
export function compare(a,b,family='any',uncertain=false) {return {bgp:overlap(observed(a,family,uncertain),observed(b,family,uncertain)),exchanges:overlap(locations(a,'exchanges',family),locations(b,'exchanges',family)),facilities:overlap(locations(a,'facilities'),locations(b,'facilities'))};}
export function validateNetwork(value) {
  const number=asn(value?.asn);const result={asn:number};
  if(value?.bgp?.ok){const b=value.bgp;result.bgp=bgp({status:'ok',data:{resource:number,query_starttime:b.observed_at,query_endtime:b.observed_until,neighbours:(b.neighbours||[]).map(r=>({asn:r.asn,type:r.type,v4_peers:r.v4,v6_peers:r.v6}))}},number,b.checked_at);}else result.bgp={ok:false,error:bounded(value?.bgp?.error)||'BGP evidence unavailable'};
  if(value?.directory?.ok){const d=value.directory;result.directory=directory({data:d.listed?[{asn:number,id:d.net_id,name:d.name,updated:d.updated_at,netixlan_set:(d.exchanges||[]).map(r=>({ix_id:r.id,ixlan_id:r.lan_id,name:r.name,ipaddr4:r.ipv4?'present':null,ipaddr6:r.ipv6?'present':null,updated:r.updated_at,status:'ok'})),netfac_set:(d.facilities||[]).map(r=>({fac_id:r.id,name:r.name,city:r.city,country:r.country,updated:r.updated_at,status:'ok'}))}]:[]},number,d.checked_at);}else result.directory={ok:false,error:bounded(value?.directory?.error)||'Directory evidence unavailable'};
  if(value?.bgp?.error&&result.bgp.ok)result.bgp.error=bounded(value.bgp.error);if(value?.directory?.error&&result.directory.ok)result.directory.error=bounded(value.directory.error);
  return result;
}
export function readPair(value) {if(value?.format!=='backbonecompare-pair'||value.version!==1||!Array.isArray(value.networks)||value.networks.length!==2)throw new Error('Choose a Backbone Compare pair JSON file.');const networks=value.networks.map(validateNetwork);if(networks[0].asn===networks[1].asn)throw new Error('Choose two different ASNs.');return {format:value.format,version:1,saved_at:validDate(value.saved_at)?value.saved_at:null,networks,notes:bounded(value.notes,4000),label:bounded(value.label,100)};}
export function pair(networks,notes,label) {return {format:'backbonecompare-pair',version:1,saved_at:new Date().toISOString(),networks,notes,label};}
export const csvValue = value => '"'+(/^[=+@\-\t\r]/.test(String(value))?"'":'')+String(value).replaceAll('"','""')+'"';
export function evidenceCsv(networks,family='any',uncertain=false) {const lines=[['Kind','ASN','Identifier','Name','Position','IPv4 evidence','IPv6 evidence','Observed at','Checked at']];for(const net of networks){for(const row of observed(net,family,uncertain)?.values()||[])lines.push(['BGP neighbour',net.asn,row.id,row.name,row.types.join('/'),row.ipv4,row.ipv6,net.bgp.observed_at||'',net.bgp.checked_at]);for(const kind of ['exchanges','facilities'])for(const row of locations(net,kind,family)?.values()||[])lines.push([kind,net.asn,row.id,row.name,'',kind==='exchanges'?row.ipv4:'',kind==='exchanges'?row.ipv6:'',row.updated_at||'',net.directory.checked_at]);}return lines.map(row=>row.map(csvValue).join(',')).join('\r\n');}

// Lightweight name directory; deliberately excludes contacts and evidence memberships.
export function providers(body){
  if(!body||!Array.isArray(body.data)||body.data.length>100)throw new Error('Invalid provider directory response.');
  const seen=new Set();return body.data.map(row=>{
    if(!row||typeof row.asn!=='number'||!Number.isInteger(row.id)||row.id<1||typeof row.name!=='string'||!row.name.trim())throw new Error('Invalid provider directory entry.');
    const number=asn(row.asn);if(seen.has(number))throw new Error('Duplicate provider directory entry.');seen.add(number);
    return {asn:number,id:row.id,name:bounded(row.name,500),aka:bounded(row.aka,500),name_long:bounded(row.name_long,500)};
  });
}
export function matchingProviders(rows,term){
  const query=String(term).trim().toLowerCase().replace(/^as(?=\d+$)/,'');
  return rows.filter(row=>[row.asn,row.name,row.aka,row.name_long].join(' ').toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name));
}
