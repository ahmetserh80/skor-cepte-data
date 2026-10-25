import {appendFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

export function needsCollection(data, now = Date.now(), force = false) {
  if (force) return true;
  const started = Date.parse(data.collection_started_at ?? data.last_success_at);
  if (!Number.isFinite(started) || started > now + 300000) throw Error('Invalid source clock');
  return started < Math.floor(now / 900000) * 900000;
}

async function main() {
  const base = process.env.SKOR_DATA_BASE_URL;
  if (base !== 'https://skor-cepte-service.spry-whale-0977.chatgpt.site') throw Error('Unexpected service');
  async function read(path) {
    const r = await fetch(base + path, {redirect:'error', signal:AbortSignal.timeout(30000)});
    if (!r.ok || !r.headers.get('content-type')?.includes('application/json')) throw Error('Public data unavailable');
    return r.json();
  }
  const registry = await read('/data/provinces.json');
  if (!Array.isArray(registry) || registry.length !== 81) throw Error('Incomplete live registry');
  const province = registry.find(p => p.status === 'ready' && !p.last_error_at);
  let needed = true;
  if (province) {
    if (!/^(?:[1-9]|[1-7][0-9]|8[01])$/.test(province.id)) throw Error('Invalid province');
    const snapshot = await read('/data/provinces/' + province.id + '.json');
    if (snapshot.province_id !== province.id) throw Error('Province mismatch');
    needed = needsCollection(snapshot, Date.now(), process.env.FORCE_COLLECTION === 'true');
  }
  appendFileSync(process.env.GITHUB_OUTPUT, 'needed=' + needed + '\n');
  console.log(JSON.stringify({collection_needed:needed}));
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
