import os
import logging
import requests
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import jwt
import datetime
from functools import wraps

# Configurações do Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Modelos
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    reviews = db.relationship('Review', order_by='Review.id', back_populates='user')
    user_books = db.relationship('UserBook', order_by='UserBook.id', back_populates='user')

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    author = db.Column(db.String(100))
    published_date = db.Column(db.Date)
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    language = db.Column(db.String(50))
    image = db.Column(db.String(255))
    pages = db.Column(db.Integer)
    publisher = db.Column(db.String(100))
    reviews = db.relationship('Review', order_by='Review.id', back_populates='book')
    user_books = db.relationship('UserBook', order_by='UserBook.id', back_populates='book')

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    review = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    book = db.relationship('Book', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')

class UserBook(db.Model):
    __tablename__ = 'user_books'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    user = db.relationship('User', back_populates='user_books')
    book = db.relationship('Book', back_populates='user_books')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Rotas da API
@app.route('/', methods = ["GET"])
def home():
    return "Welcome to libruary API!"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Username already exists'}), 400

    try:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Registered successfully!'})
    except Exception as e:
        return jsonify({'message': 'Registration failed', 'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Login failed!'}), 401

    # Geração do token JWT
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'message': 'Logged in successfully!', 'token': token})


@app.route('/books', methods=['GET'])
def get_books():
    try:
        books = Book.query.all()
        output = [{
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'published_date': book.published_date,
            'isbn': book.isbn,
            'language': book.language,
            'image': book.image,
            'pages': book.pages,
            'publisher': book.publisher
        } for book in books]
        return jsonify({'books': output})
    except Exception as e:
        return jsonify({'message': 'Error fetching books', 'error': str(e)}), 500

@app.route('/book/<int:book_id>', methods=['GET'])
def get_book(book_id):
    try:
        book = Book.query.get(book_id)
        if book is None:
            return jsonify({'message': 'Book not found'}), 404

        output = {
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'published_date': book.published_date,
            'isbn': book.isbn,
            'language': book.language,
            'image': book.image,
            'pages': book.pages,
            'publisher': book.publisher
        }
        return jsonify({'book': output})
    except Exception as e:
        return jsonify({'message': 'Error fetching book', 'error': str(e)}), 500

@app.route('/review', methods=['POST'])
@token_required
def add_review():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    book_id = data.get('book_id')
    user_id = data.get('user_id')
    review_text = data.get('review_text')
    rating = data.get('rating')

    if not book_id or not user_id or not review_text or rating is None:
        return jsonify({'message': 'Book ID, User ID, Review text, and Rating are required'}), 400

    try:
        new_review = Review(book_id=book_id, user_id=user_id, review=review_text, rating=rating)
        db.session.add(new_review)
        db.session.commit()
        return jsonify({'message': 'Review added successfully!'})
    except Exception as e:
        return jsonify({'message': 'Error adding review', 'error': str(e)}), 500

@app.route('/profile/<int:user_id>', methods=['GET'])
@token_required
def get_profile(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        reviews = Review.query.filter_by(user_id=user_id).all()
        review_list = [{'book_id': review.book_id, 'review': review.review, 'rating': review.rating} for review in reviews]
        return jsonify({'username': user.username, 'reviews': review_list})
    except Exception as e:
        return jsonify({'message': 'Error fetching profile', 'error': str(e)}), 500

@app.route('/add_book', methods=['POST'])
@token_required
def add_book():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    isbn = data.get('isbn')
    user_id = data.get('user_id')

    if not isbn or not user_id:
        return jsonify({'message': 'ISBN and user ID are required'}), 400

    book = Book.query.filter_by(isbn=isbn).first()

    if not book:
        google_books_url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}'
        try:
            response = requests.get(google_books_url)
            response.raise_for_status()
            book_data = response.json().get('items', [])

            if not book_data:
                return jsonify({'message': 'Book not found in Google Books API'}), 404

            book_info = book_data[0].get('volumeInfo', {})
            title = book_info.get('title', 'N/A')
            author = ', '.join(book_info.get('authors', []))
            language = book_info.get('language', 'N/A')
            image = book_info.get('imageLinks', {}).get('thumbnail')
            pages = book_info.get('pageCount')
            publisher = book_info.get('publisher')

            def format_published_date(published_date):
                try:
                    return datetime.datetime.strptime(published_date, '%Y-%m-%d').date()
                except ValueError:
                    return datetime.datetime.strptime(published_date, '%Y').date().replace(day=1, month=1)

            published_date = format_published_date(book_info.get('publishedDate', '1000'))

            book = Book(
                title=title,
                author=author,
                published_date=published_date,
                isbn=isbn,
                language=language,
                image=image,
                pages=pages,
                publisher=publisher
            )
            db.session.add(book)
            db.session.commit()
        except requests.exceptions.RequestException as e:
            app.logger.error(f'Error fetching book data from Google Books API: {e}')
            return jsonify({'message': 'Error fetching book data from Google Books API', 'error': str(e)}), 500

    user_book = UserBook.query.filter_by(user_id=user_id, book_id=book.id).first()
    if user_book:
        return jsonify({'message': 'Book already added to user library'}), 400

    try:
        user_book = UserBook(user_id=user_id, book_id=book.id)
        db.session.add(user_book)
        db.session.commit()
        return jsonify({'message': 'Book added to user library successfully!'})
    except Exception as e:
        app.logger.error(f'Error adding book to user library: {e}')
        return jsonify({'message': 'Error adding book to user library', 'error': str(e)}), 500

@app.route('/book_reviews/<string:isbn>', methods=['GET'])
def get_book_reviews(isbn):
    try:
        book = Book.query.filter_by(isbn=isbn).first()
        if not book:
            return jsonify({'message': 'Book not found'}), 404

        reviews = Review.query.filter_by(book_id=book.id).all()
        review_list = [{'id': review.id, 'user_id': review.user_id, 'review': review.review, 'rating': review.rating} for review in reviews]

        return jsonify({'book': {
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'isbn': book.isbn
        }, 'reviews': review_list})
    except Exception as e:
        app.logger.error(f'Error fetching book reviews: {e}')
        return jsonify({'message': 'Error fetching book reviews', 'error': str(e)}), 500

@app.route('/user_books/<int:user_id>', methods=['GET'])
def get_user_books(user_id):
    # Verifique se o usuário existe
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Verifique se o usuário tem livros
    user_books = UserBook.query.filter_by(user_id=user_id).all()
    if not user_books:
        return jsonify({'message': 'No books found for this user'}), 404

    # Obtenha os livros do usuário
    output = [{'book_id': user_book.book_id} for user_book in user_books]
    return jsonify({'user_books': output})

@app.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f'Error occurred: {e}')
    return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(host='0.0.0.0')
