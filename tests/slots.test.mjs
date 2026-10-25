import test from 'node:test';
import assert from 'node:assert/strict';
import {needsCollection} from '../scripts/check_slot.mjs';
const now=Date.parse('2026-10-25T15:22:00Z');
test('a completed 15:00 scan does not suppress the 15:15 scan',()=>{
  assert.equal(needsCollection({collection_started_at:'2026-10-25T15:00:02Z',last_success_at:'2026-10-25T15:09:58Z'},now),true);
});
test('external timer and delayed GitHub timer share one quarter-hour scan',()=>{
  assert.equal(needsCollection({collection_started_at:'2026-10-25T15:15:08Z'},now),false);
});
test('next quarter, midnight and day boundaries trigger a new scan',()=>{
  for(const [start,time] of [['15:15:08','15:30:00'],['23:45:00','00:00:00']]) {
    const nextDate=time==='00:00:00'?'26':'25';
    assert.equal(needsCollection({collection_started_at:'2026-10-25T'+start+'Z'},Date.parse('2026-10-'+nextDate+'T'+time+'Z')),true);
  }
});
test('bad/future clocks never silently label a stale feed current',()=>{
  for(const timestamp of ['bad','2026-10-26T15:00:00Z']) assert.throws(()=>needsCollection({last_success_at:timestamp},now));
});
test('manual force and old installed source format are supported',()=>{
  assert.equal(needsCollection({last_success_at:'2026-10-25T15:16:00Z'},now),false);
  assert.equal(needsCollection({last_success_at:'2026-10-25T15:16:00Z'},now,true),true);
});
