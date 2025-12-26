"""
SpaCy NLP HTTP Service
Provides POS tagging, NER, and text processing via REST API
"""
from flask import Flask, request, jsonify
import spacy
from typing import Dict, List

app = Flask(__name__)

# Load models on startup (lazy loading per request optional)
models: Dict[str, spacy.Language] = {}

def load_model(model_name: str) -> spacy.Language:
    """Load spaCy model with caching"""
    if model_name not in models:
        models[model_name] = spacy.load(model_name)
    return models[model_name]

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'models_loaded': list(models.keys())})

@app.route('/process', methods=['POST'])
def process_text():
    """
    Process text with spaCy

    Request JSON:
    {
      "text": "Your text here",
      "model": "en_core_web_sm",  // optional, default: en_core_web_sm
      "features": ["pos", "ner"]  // optional, default: all
    }

    Response JSON:
    {
      "tokens": [
        {"text": "Your", "pos": "PRON", "tag": "PRP$", "lemma": "your"},
        ...
      ],
      "entities": [
        {"text": "Apple", "label": "ORG", "start": 0, "end": 5},
        ...
      ]
    }
    """
    data = request.get_json()
    text = data.get('text', '')
    model_name = data.get('model', 'en_core_web_sm')
    features = data.get('features', ['pos', 'ner'])

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        nlp = load_model(model_name)
        doc = nlp(text)

        response = {}

        if 'pos' in features:
            response['tokens'] = [
                {
                    'text': token.text,
                    'pos': token.pos_,
                    'tag': token.tag_,
                    'lemma': token.lemma_,
                    'is_punct': token.is_punct,
                    'is_stop': token.is_stop
                }
                for token in doc
            ]

        if 'ner' in features:
            response['entities'] = [
                {
                    'text': ent.text,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                }
                for ent in doc.ents
            ]

        return jsonify(response)

    except OSError:
        return jsonify({'error': f'Model {model_name} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Pre-load default model
    load_model('en_core_web_sm')
    # Run on all interfaces for container networking
    app.run(host='0.0.0.0', port=8081)
