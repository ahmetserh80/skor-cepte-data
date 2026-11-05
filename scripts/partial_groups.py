"""Advance verified groups while retaining failed groups at their real old clocks."""
from copy import deepcopy
from source_reader import SourceError

def merge_verified_groups(previous, current):
    old = {g['id']:g for g in previous.get('groups',[])}
    fresh = {g['id']:g for g in current['groups']}
    if len(fresh) != len(current['groups']):
        raise SourceError('Repeated competition identity')
    for ident,g in fresh.items():
        if ident in old and old[ident]['competition']['value'] != g['competition']['value']:
            raise SourceError('Competition identity changed')
    unverified = {c['value'].split('*')[0]:c for c in current.get('unverified_competitions',[])}
    empty = {c['value'].split('*')[0] for c in current.get('empty_competitions',[])}
    errors=[];preserved=[]
    for ident,g in old.items():
        if ident in fresh:
            continue
        issue=unverified.get(ident)
        reason=issue['reason'] if issue else 'Source group is empty' if ident in empty else 'Source group is absent from the current menu'
        kind='validation' if issue else 'source_empty' if ident in empty else 'source_missing'
        kept=deepcopy(g)
        kept['source_state']='preserved'
        kept['source_error']={'kind':kind,'reason':reason}
        # checked_at remains exactly the last verified source clock.
        current['groups'].append(kept);preserved.append(ident)
        errors.append({'id':ident,'label':g['competition']['label'],'reason':reason,'kind':kind,'retained':True})
    for ident,issue in unverified.items():
        if ident in old:
            continue
        errors.append({'id':ident,'label':issue['label'],'reason':issue['reason'],'kind':'validation','retained':False})
    if errors:
        for ident,g in fresh.items():
            g['source_state']='fresh'
            g.pop('source_error',None)
        current.update(partial_update=True,group_errors=errors,
                       preserved_group_ids=preserved,fresh_group_ids=list(fresh))
        current['unverified_competitions']=[c for c in current.get('unverified_competitions',[])if c['value'].split('*')[0]not in preserved]
        if old:
            current['last_success_at']=previous['last_success_at']
        current['groups'].sort(key=lambda g:(g.get('category',''),g.get('gender',''),g.get('title',''),g['id']))
    return current
