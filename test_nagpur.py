import urllib.request, json

payload = {
    'session_id': 'test_user',
    'message': 'plan a trip to nagpur for 3 adults for 5 days',
    'session_id': 'test_user_123'
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/chat/message',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode())
        print('Status:', resp.status)
        trip = body.get('trip', {})
        print('Trip title:', trip.get('title'))
        print('Destination:', trip.get('destination'))
        print('Days:', trip.get('day_count'))
        hotel = trip.get('hotel')
        print('Hotel:', hotel.get('name', 'None') if hotel else 'None')
        print('Hotel category:', hotel.get('category', 'None') if hotel else 'None')
        print('Flight ID:', trip.get('flight_id', 'None'))
        # Check stops for photos
        for day in trip.get('days', []):
            for stop in day.get('stops', []):
                place = stop.get('place', {})
                if place:
                    photos = place.get('photos', [])
                    source = place.get('source', 'unknown')
                    print(f"  Stop: {place.get('name')} - Photos: {len(photos)} - Source: {source}")
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    print(e.read().decode()[:500])
except Exception as e:
    print('Error:', type(e).__name__, str(e)[:300])