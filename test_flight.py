import urllib.request, json

payload = {
    'cabin': 'Economy',
    'adults': 1,
    'children': 0,
    'infants_seat': 0,
    'infants_lap': 0,
    'currency': 'INR',
    'live': True,
    'trip_type': 'one-way',
    'max_results': None,
    'origin': 'DEL',
    'destination': 'BOM',
    'outbound_date': '2026-12-16'
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/flights/search',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode())
        print('Status:', resp.status)
        print('Count:', body.get('count'))
        print('Source:', body.get('source'))
        if body.get('flights'):
            for f in body['flights'][:5]:
                print(f'  {f["airline"]} {f["flight_number"]} {f["origin"]}->{f["destination"]} price={f["price_usd"]} source={f.get("source")}')
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    print(e.read().decode()[:500])
except Exception as e:
    print('Error:', type(e).__name__, str(e)[:300])