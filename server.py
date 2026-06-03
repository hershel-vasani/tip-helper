import os
import base64
import json
from flask import Flask, request, jsonify

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    import anthropic

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set'}), 500

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': 'No image provided'}), 400

    # image is base64 data URL: "data:image/jpeg;base64,..."
    header, b64 = data['image'].split(',', 1)
    media_type = header.split(':')[1].split(';')[0]  # e.g. image/jpeg

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=256,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': b64,
                    }
                },
                {
                    'type': 'text',
                    'text': (
                        'This is a photo of a restaurant or food service receipt. '
                        'Reply with ONLY valid JSON, no other text. '
                        'Find the final amount the customer owes (labeled Total, Amount Due, Balance Due, Grand Total, etc.). '
                        'Also check if gratuity/tip/service charge is already included. '
                        'JSON format: {"total": <number or null>, "tip_included": <true or false>, "tip_label": "<label found or null>"}'
                    )
                }
            ]
        }]
    )

    raw = response.content[0].text.strip()
    # strip markdown code fences if present
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    result = json.loads(raw)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5005))
    app.run(host='0.0.0.0', port=port, debug=False)
