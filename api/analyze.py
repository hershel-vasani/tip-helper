from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os

PROMPT = (
    'This is a photo of a restaurant or food service receipt. '
    'Reply with ONLY valid JSON, no other text.\n'
    '1) Find the final amount the customer owes (labeled Total, Amount Due, Balance Due, Grand Total, etc.).\n'
    '2) Determine whether a tip/gratuity/service charge has ALREADY been added to that total. '
    'This is common for large parties. Look for any line such as: Gratuity, Auto Gratuity, Auto Grat, '
    'Service Charge, Svc Chg, Srv Chg, Tip, Tip Included, "18% added", "20% gratuity", or a mandatory/suggested '
    'service fee that is part of the total. Set tip_included to true ONLY if such a charge is actually included '
    'in the total (ignore blank tip lines the customer is meant to fill in themselves).\n'
    '3) If tip_included is true, put the exact wording/percent you saw in tip_label (e.g. "Gratuity 18%").\n'
    'JSON format: {"total": <number or null>, "tip_included": <true or false>, "tip_label": "<label found or null>"}'
)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Passcode gate (only enforced if APP_PASSCODE is configured)
            passcode = os.environ.get('APP_PASSCODE')
            if passcode:
                qs = parse_qs(urlparse(self.path).query)
                provided = qs.get('key', [None])[0] or self.headers.get('X-App-Key')
                if provided != passcode:
                    return self._json(401, {'error': 'Not authorized'})

            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                return self._json(500, {'error': 'ANTHROPIC_API_KEY not set'})

            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            if not data or 'image' not in data:
                return self._json(400, {'error': 'No image provided'})

            # image is base64 data URL: "data:image/jpeg;base64,..."
            header, b64 = data['image'].split(',', 1)
            media_type = header.split(':')[1].split(';')[0]

            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=256,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': b64}},
                        {'type': 'text', 'text': PROMPT},
                    ],
                }],
            )

            raw = response.content[0].text.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            return self._json(200, json.loads(raw))
        except Exception as e:
            return self._json(500, {'error': str(e)})

    def _json(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
