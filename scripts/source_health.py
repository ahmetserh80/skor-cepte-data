"""Persist incident state with the published registry, without changing clocks."""
from datetime import datetime, timezone, timedelta
import json, os
from pathlib import Path


def evaluate(registry, errors, started_at):
    now = datetime.fromisoformat(started_at)
    failed = {error['province']: error for error in errors}
    alerts = []
    recovered = []
    for province in registry:
        error = failed.get(province['name'])
        if error is None:
            if province.get('first_error_at'):
                recovered.append(province['name'])
            for key in ('first_error_at', 'error_alerted_at', 'last_error_kind'):
                province.pop(key, None)
            continue
        first = province.setdefault('first_error_at', started_at)
        try:
            duration = now - datetime.fromisoformat(first)
            if duration < timedelta(0):
                raise ValueError('Future incident clock')
        except (ValueError, TypeError):
            province['first_error_at'] = started_at
            duration = timedelta(0)
        # Initial isolated timeouts are warnings. Validation/feed failures,
        # widespread outages or a continuous 45-minute outage warrant an alert.
        critical = (province.get('last_error_kind') != 'transport'
                    or len(errors) >= 4 or duration >= timedelta(minutes=45))
        if critical and not province.get('error_alerted_at'):
            province['error_alerted_at'] = started_at
            alerts.append(province['name'])
    return {'alerts': alerts, 'recovered': recovered, 'source_errors': len(errors)}


def main():
    report = json.loads(Path('collection-report.json').read_text())
    if not isinstance(report.get('errors'), list) or 'health' not in report:
        raise ValueError('Collection health report is missing or invalid')
    print(json.dumps(report, ensure_ascii=False))
    summary = ('## Veri yenileme\n\n'
               f"Doğrulanan il: {report['checked']}/81\n\n"
               f"Kaynak aksaklığı: {len(report['errors'])}\n\n")
    for error in report['errors']:
        summary += f"- {error['province']}: {error['error']} (önceki veri korunuyor)\n"
    for province in report['health'].get('recovered', []):
        summary += f"- {province}: kaynak bağlantısı düzeldi.\n"
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(summary)
    if report['errors']:
        print('::warning::Bazı il kaynakları okunamadı; eski kayıtlar ve gerçek güncelleme saatleri korundu. Ayrıntılar çalışma özetinde.')
    if report['health']['alerts']:
        raise SystemExit('New source incident: ' + ', '.join(report['health']['alerts']))


if __name__ == '__main__':
    main()
