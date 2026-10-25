export function notificationTitle(events) {
  const kinds=new Set(events.map(e=>e.kind)),parts=[];
  if(kinds.has('match')||kinds.has('schedule'))parts.push('Maç takvimi');
  if(kinds.has('score'))parts.push(parts.length?'maç skoru':'Maç skoru');
  if(kinds.has('rank'))parts.push(parts.length?'sıralama değişikliği':'Sıralama değişikliği');
  return parts.length>1?parts.slice(0,-1).join(', ')+' ve '+parts.at(-1):parts[0]||'Yeni gelişme';
}

// Group only the same fixture in the same source check, after preference filtering.
export function notificationCards(events) {
  const buckets=new Map();
  for(const e of events){
    const key=e.matchKey?JSON.stringify([e.matchKey,e.at]):e.id;
    if(!buckets.has(key))buckets.set(key,[]);
    buckets.get(key).push(e);
  }
  return [...buckets.values()].map(items=>{
    const latest=items.at(-1),structured=items.every(e=>e.detail&&e.teams);
    const details=items.map(e=>(items.length>1?(e.kind==='score'?'Skor: ':'Takvim: '):'')+e.detail);
    return {title:notificationTitle(items),subtitle:[latest.provinceName,latest.title].filter(Boolean).join(' · '),
      body:structured?latest.teams.join(' – ')+'\n'+details.join('\n'):items.map(e=>e.text).join('\n'),
      group:latest.group,at:latest.at,events:items};
  });
}
