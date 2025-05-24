import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
from werkzeug.utils import escape
from werkzeug.exceptions import BadRequest
from sqlalchemy import Index
import requests
from langdetect import detect

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize Flask-SocketIO with threading mode for simplicity
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///feedback.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['DWANI_API_KEY'] = os.getenv('DWANI_API_KEY', 'mohammedsabeel063@gmail.com_dwani_krishnadevaraya')
app.config['DWANI_API_BASE_URL'] = os.getenv('DWANI_API_BASE_URL', 'https://dwani-krishnadevaraya.hf.space')

db = SQLAlchemy(app)

class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    text_translated = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(10), nullable=False, default='en')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    userId = db.Column(db.String(50), nullable=True)
    
    __table_args__ = (
        Index('idx_category', 'category'),
        Index('idx_timestamp', 'timestamp'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'fullName': self.name,
            'location': self.location,
            'feedback': self.text,
            'text_translated': self.text_translated,
            'category': self.category,
            'language': self.language,
            'date_submitted': self.timestamp.isoformat(),
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'status': self.status,
            'userId': self.userId or f'user_{self.id}'
        }

def translate_text(text, source_lang, target_lang='en'):
    try:
        api_key = app.config["DWANI_API_KEY"]
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
        src_lang = INDICTRANS_LANG_CODES.get(source_lang.lower(), 'eng_Latn')
        tgt_lang = INDICTRANS_LANG_CODES.get(target_lang, 'eng_Latn')
        data = {
            "sentences": [text],
            "src_lang": src_lang,
            "tgt_lang": tgt_lang
        }
        url = f"{app.config['DWANI_API_BASE_URL']}/v1/translate?api_key={api_key}"
        app.logger.info(f"Translating text: {text[:100]}...")
        app.logger.info(f"Source language: {src_lang}, Target language: {tgt_lang}")
        app.logger.info(f"Requesting: {url}")
        app.logger.info(f"Headers: {headers}")
        app.logger.info(f"Data: {data}")

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )
        app.logger.info(f"Response Status: {response.status_code}")
        app.logger.info(f"Response Body: {response.text[:500]}...")

        if response.status_code == 200:
            translations = response.json().get('translations')
            if translations and len(translations) > 0:
                translated_text = translations[0]
                app.logger.info(f"Translated text: {translated_text}")
                # Check if translation is the same as the original text (indicating a potential failure)
                if translated_text.strip() == text.strip():
                    app.logger.warning(f"Translation returned the same text as the original: {text}")
                    return "[Translation Failed - Same as Original]"
                return translated_text
            else:
                app.logger.warning("No translations returned from Dwani API")
                return "[Translation Failed - No Translations]"
        else:
            app.logger.error(f"Translation failed with status {response.status_code}: {response.text}")
            return f"[Translation Failed - HTTP {response.status_code}]"
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Network error during translation: {str(e)}")
        return "[Translation Failed - Network Error]"
    except Exception as e:
        app.logger.error(f"Unexpected error during translation: {str(e)}")
        return "[Translation Failed - Unexpected Error]"

def validate_input(data, required_fields):
    missing = []
    invalid = []
    normalized_data = {}
    
    for field in required_fields:
        if field == 'name':
            value = data.get('name') or data.get('fullName')
        elif field == 'text':
            value = data.get('text') or data.get('feedback')
        else:
            value = data.get(field)
        
        if not value or value == 'undefined' or (isinstance(value, str) and not value.strip()):
            missing.append(field)
        elif field in ['name', 'text']:
            stripped_value = value.strip()
            if len(stripped_value) < 2:
                invalid.append(f"{field} is too short (minimum 2 characters)")
            elif stripped_value.lower() == 'undefined':
                invalid.append(f"{field} cannot be 'undefined'")
            else:
                normalized_data[field] = escape(stripped_value)
        else:
            normalized_data[field] = escape(value.strip()) if isinstance(value, str) else value

    if missing:
        app.logger.error(f"Missing fields: {', '.join(missing)}")
        raise BadRequest(f"Missing required fields: {', '.join(missing)}")
    
    if invalid:
        app.logger.error(f"Invalid fields: {', '.join(invalid)}")
        raise BadRequest(f"Invalid input: {', '.join(invalid)}")
    
    other_category = data.get('otherCategory', '').strip()
    if other_category and normalized_data['category'] == 'Other':
        if len(other_category) < 2:
            app.logger.error("otherCategory is too short")
            raise BadRequest("Other category specification must be at least 2 characters")
        normalized_data['category'] = f"Other: {escape(other_category)}"
    
    app.logger.info(f"Normalized data: {normalized_data}")
    return normalized_data

def detect_language(text):
    try:
        detected_lang = detect(text)
        # Map langdetect codes to our supported languages
        lang_map = {
            'hi': 'hi',
            'kn': 'kn',
            'te': 'te',
            'ta': 'ta',
            'bn': 'bn',
            'gu': 'gu',
            'ml': 'ml',
            'mr': 'mr',
            'pa': 'pa',
            'or': 'or',
            'as': 'as',
            'en': 'en'
        }
        return lang_map.get(detected_lang, 'en')
    except Exception as e:
        app.logger.warning(f"Language detection failed: {str(e)}. Defaulting to 'en'.")
        return 'en'

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "Citizen Feedback API is running",
        "endpoints": {
            "submit_feedback": "/api/v1/feedback (POST)",
            "get_feedbacks": "/api/v1/feedback (GET)",
            "test_dwani_api": "/api/v1/test-dwani (GET)",
            "test_translation": "/api/v1/test-translation (POST)"
        }
    })

@app.route('/api/v1/feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.get_json()
        if not data:
            app.logger.error("No JSON data received")
            raise BadRequest("No JSON data received")
            
        app.logger.info(f"Received feedback data: {data}")
            
        data = validate_input(data, ['name', 'location', 'text', 'category', 'language'])
        
        source_lang = data.get('language').lower()
        
        SUPPORTED_LANGS = {'hi', 'kn', 'te', 'ta', 'bn', 'gu', 'ml', 'mr', 'pa', 'or', 'as', 'en'}
        if source_lang not in SUPPORTED_LANGS:
            app.logger.warning(f"Provided language {source_lang} not supported, defaulting to 'en'")
            source_lang = 'en'
        
        # Detect the actual language of the feedback text
        detected_lang = detect_language(data['text'])
        if detected_lang != source_lang:
            app.logger.warning(f"Detected language {detected_lang} does not match provided language {source_lang}. Using detected language.")
            source_lang = detected_lang
        
        # Always translate the feedback to English
        app.logger.info("Attempting translation to English...")
        text_translated = translate_text(data['text'], source_lang)
        app.logger.info(f"Translation result: {text_translated[:100] if text_translated else 'None'}")
        
        feedback = Feedback(
            name=data['name'],
            location=data['location'],
            text=data['text'],
            text_translated=text_translated,
            category=data['category'],
            language=source_lang,
            timestamp=datetime.utcnow(),
            status='pending',
            userId=data.get('userId', f'user_{datetime.utcnow().timestamp()}')
        )
        
        db.session.add(feedback)
        db.session.commit()
        
        app.logger.info(f"Feedback saved successfully with ID: {feedback.id}")
        
        # Broadcast feedback via WebSocket
        feedback_data = feedback.to_dict()
        app.logger.info(f"Attempting to broadcast feedback to namespace /ws: {feedback_data}")
        socketio.emit('new_feedback', feedback_data, namespace='/ws')
        app.logger.info(f"Successfully broadcasted new feedback via WebSocket: {feedback_data}")

        return jsonify({
            "status": "success",
            "message": "Feedback submitted successfully",
            "data": feedback_data
        }), 201
        
    except BadRequest as e:
        app.logger.error(f"Bad request: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error submitting feedback: {str(e)}")
        app.logger.error(f"Error type: {type(e).__name__}")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error_details": str(e)
        }), 500

@app.route('/api/v1/feedback', methods=['GET'])
def get_feedbacks():
    try:
        search_query = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Feedback.query
        
        if search_query:
            query = query.filter(
                Feedback.text.ilike(f'%{search_query}%') |
                Feedback.text_translated.ilike(f'%{search_query}%') |
                Feedback.category.ilike(f'%{search_query}%') |
                Feedback.name.ilike(f'%{search_query}%')
            )
        
        feedbacks = query.order_by(Feedback.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        
        # Ensure all feedbacks have a translated version and correct language
        for feedback in feedbacks.items:
            # Check and correct the language based on the feedback text
            detected_lang = detect_language(feedback.text)
            if feedback.language != detected_lang:
                app.logger.info(f"Correcting language for feedback ID {feedback.id} from {feedback.language} to {detected_lang}")
                feedback.language = detected_lang
            
            # Retry translation if it failed or is missing
            if (not feedback.text_translated or 
                feedback.text_translated.startswith("[Translation Failed") or 
                feedback.text_translated == feedback.text):
                app.logger.info(f"Retranslating feedback ID {feedback.id} to English...")
                feedback.text_translated = translate_text(feedback.text, feedback.language)
                app.logger.info(f"Translation result for ID {feedback.id}: {feedback.text_translated[:100] if feedback.text_translated else 'None'}")
        
        db.session.commit()
        
        return jsonify([fb.to_dict() for fb in feedbacks.items])
    except Exception as e:
        app.logger.error(f"Error fetching feedbacks: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    try:
        total_feedbacks = Feedback.query.count()
        resolved = Feedback.query.filter_by(status='resolved').count()
        pending = Feedback.query.filter_by(status='pending').count()
        unique_users = db.session.query(db.func.count(db.distinct(Feedback.userId))).scalar()

        last_month = datetime.utcnow().replace(day=1)
        last_month_feedbacks = Feedback.query.filter(Feedback.timestamp < last_month).count()
        total_feedbacks_change = ((total_feedbacks - last_month_feedbacks) / last_month_feedbacks * 100) if last_month_feedbacks else 0

        return jsonify({
            "totalFeedbacks": total_feedbacks,
            "resolved": resolved,
            "pending": pending,
            "uniqueUsers": unique_users,
            "totalFeedbacksChange": round(total_feedbacks_change, 1),
            "resolvedChange": 0,
            "pendingChange": 0,
            "uniqueUsersChange": 0
        })
    except Exception as e:
        app.logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/api/v1/trends', methods=['GET'])
def get_trends():
    try:
        feedbacks = Feedback.query.all()
        weekly = {}
        monthly = {}
        yearly = {}

        for feedback in feedbacks:
            date = feedback.timestamp
            week_start = date - timedelta(days=date.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            weekly[week_key] = weekly.get(week_key, 0) + 1

            month_key = date.strftime("%Y-%m")
            monthly[month_key] = monthly.get(month_key, 0) + 1

            year_key = date.strftime("%Y")
            yearly[year_key] = yearly.get(year_key, 0) + 1

        weekly_data = [{"date": k, "count": v} for k, v in sorted(weekly.items())][-7:]
        monthly_data = [{"date": k, "count": v} for k, v in sorted(monthly.items())][-12:]
        yearly_data = [{"date": k, "count": v} for k, v in sorted(yearly.items())][-5:]

        return jsonify({
            "weekly": weekly_data,
            "monthly": monthly_data,
            "yearly": yearly_data
        })
    except Exception as e:
        app.logger.error(f"Error fetching trends: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/api/v1/test-dwani', methods=['GET'])
def test_dwani_api():
    try:
        headers = {
            'X-API-Key': app.config["DWANI_API_KEY"],
            'Content-Type': 'application/json'
        }
        
        test_data = {
            "sentences": ["ಹಲೋ ಯಾರೋ ನೀವು"],
            "src_lang": "kan_Knda",
            "tgt_lang": "eng_Latn"
        }
        
        response = requests.post(
            f"{app.config['DWANI_API_BASE_URL']}/v1/translate?api_key={app.config['DWANI_API_KEY']}",
            headers=headers,
            json=test_data
        )
        
        app.logger.info(f"DWANI API Request URL: {response.request.url}")
        app.logger.info(f"DWANI API Request Headers: {response.request.headers}")
        app.logger.info(f"DWANI API Request Body: {response.request.body}")
        app.logger.info(f"DWANI API Response Status: {response.status_code}")
        app.logger.info(f"DWANI API Response: {response.text}")
        
        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "DWANI API is working correctly",
                "dwani_api_status": response.status_code,
                "dwani_api_response": response.json(),
                "request_details": {
                    "url": response.request.url,
                    "headers": dict(response.request.headers),
                    "body": test_data
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": "DWANI API returned an error",
                "dwani_api_status": response.status_code,
                "dwani_api_response": response.text,
                "request_details": {
                    "url": response.request.url,
                    "headers": dict(response.request.headers),
                    "body": test_data
                }
            }), response.status_code
        
    except requests.exceptions.ConnectionError:
        return jsonify({
            "status": "error",
            "message": "Could not connect to DWANI API",
            "error": "Connection Error - Please check if the API URL is correct and the service is running"
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "DWANI API request timed out",
            "error": "Request Timeout - The API took too long to respond"
        }), 504
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to connect to DWANI API",
            "error": str(e),
            "error_type": type(e).__name__
        }), 500

@app.route('/api/v1/test-translation', methods=['POST'])
def test_translation():
    try:
        data = request.get_json()
        if not data:
            raise BadRequest("No JSON data received")
            
        text = data.get('text')
        source_lang = data.get('source_language', 'en')
        target_lang = data.get('target_language', 'en')
        
        if not text:
            raise BadRequest("Text is required")
            
        app.logger.info(f"Testing translation: {text[:100]}...")
        app.logger.info(f"From {source_lang} to {target_lang}")
        
        translated = translate_text(text, source_lang, target_lang)
        
        return jsonify({
            "status": "success",
            "original_text": text,
            "translated_text": translated,
            "source_language": source_lang,
            "target_language": target_lang
        })
        
    except BadRequest as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except Exception as e:
        app.logger.error(f"Translation test error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Translation failed",
            "error": str(e)
        }), 500

# WebSocket event handlers
@socketio.on('connect', namespace='/ws')
def handle_connect():
    app.logger.info('WebSocket client connected to /ws namespace')
    emit('status', {'message': 'Connected to WebSocket server'}, namespace='/ws')

@socketio.on('disconnect', namespace='/ws')
def handle_disconnect():
    app.logger.info('WebSocket client disconnected from /ws namespace')

@socketio.on('message', namespace='/ws')
def handle_message(message):
    app.logger.info(f'Received WebSocket message on /ws: {message}')

with app.app_context():
    db.drop_all()
    db.create_all()
    app.logger.info("Database tables recreated successfully")

INDICTRANS_LANG_CODES = {
    'hi': 'hin_Deva',
    'kn': 'kan_Knda',
    'te': 'tel_Telu',
    'ta': 'tam_Taml',
    'bn': 'ben_Beng',
    'gu': 'guj_Gujr',
    'ml': 'mal_Mlym',
    'mr': 'mar_Deva',
    'pa': 'pan_Guru',
    'or': 'ory_Orya',
    'as': 'asm_Beng',
    'en': 'eng_Latn'
}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    