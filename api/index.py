import os
import logging
import requests
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from models import db, User, Book, Review

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://a11390087689:danicravo123@aid.estgoh.ipc.pt/db11390087689')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '1234')
db.init_app(app)
migrate = Migrate(app, db)

# API Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        app.logger.error('No data provided in request')
        return jsonify({'message': 'No data provided'}), 400

    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        app.logger.error('Username or password not provided')
        return jsonify({'message': 'Username and password are required'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        app.logger.error('Username already exists')
        return jsonify({'message': 'Username already exists'}), 400

    try:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Registered successfully!'})
    except Exception as e:
        app.logger.error(f'Error occurred during registration: {e}')
        return jsonify({'message': 'Registration failed', 'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Login failed!'})
    return jsonify({'message': 'Logged in successfully!'})

@app.route('/books', methods=['GET'])
def get_books():
    response = requests.get('https://www.googleapis.com/books/v1/volumes?q=free')
    books = response.json().get('items', [])
    output = []
    for book in books:
        book_info = book.get('volumeInfo', {})
        book_data = {
            'title': book_info.get('title', 'N/A'),
            'author': ', '.join(book_info.get('authors', [])),
            'description': book_info.get('description', 'No description available')
        }
        output.append(book_data)
    return jsonify({'books': output})

@app.route('/review', methods=['POST'])
def add_review():
    data = request.get_json()
    new_review = Review(book_id=data['book_id'], user_id=data['user_id'], review=data['review_text'], rating=data['rating'])
    db.session.add(new_review)
    db.session.commit()
    return jsonify({'message': 'Review added successfully!'})

@app.route('/profile/<int:user_id>', methods=['GET'])
def get_profile(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    reviews = Review.query.filter_by(user_id=user_id).all()
    review_list = [{'book_id': review.book_id, 'review': review.review, 'rating': review.rating} for review in reviews]
    return jsonify({
        'username': user.username,
        'reviews': review_list
    })

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run()
