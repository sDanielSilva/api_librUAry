import os
import datetime
from functools import wraps
import jwt
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
#from dotenv import load_dotenv
#load_dotenv()  

# Configurações do Flask
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialização dos componentes do Flask
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
    read = db.Column(db.Boolean, default=False)
    user = db.relationship('User', back_populates='user_books')
    book = db.relationship('Book', back_populates='user_books')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token')
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(current_user, *args, **kwargs)
    return decorated


# Rotas da API
@app.route('/', methods = ["GET"])
def home():
    return "Welcome to libruary API!"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.dirname(os.path.realpath(__file__)), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/validateToken', methods=['POST'])
def validate_token():
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'message': 'Token is missing'}), 400

    try:
        # Decodifica o token JWT
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])

        exp_date = datetime.datetime.fromtimestamp(decoded_token['exp'], tz=datetime.timezone.utc)
        
        # Verifica se o token expirou
        if exp_date < datetime.datetime.now(datetime.timezone.utc):
            return jsonify({'is_valid': False, 'message': 'Token has expired'}), 401
        
        # O token é válido
        return jsonify({'is_valid': True, 'message': 'Token is valid'})
    except jwt.ExpiredSignatureError:
        # O token expirou
        return jsonify({'is_valid': False, 'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        # O token é inválido
        return jsonify({'is_valid': False, 'message': 'Invalid token'}), 401


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
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    # Inclua o userId na resposta
    return jsonify({'message': 'Logged in successfully!', 'token': token, 'user_id': user.id})

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
def add_review(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    book_id = data.get('book_id')
    review_text = data.get('review_text')
    rating = data.get('rating')

    if not book_id or not review_text or rating is None:
        return jsonify({'message': 'Book ID, Review text, and Rating are required'}), 400

    existing_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()

    if existing_review:
        existing_review.review = review_text
        existing_review.rating = rating
        message = 'Review updated successfully!'
    else:
        new_review = Review(book_id=book_id, user_id=current_user.id, review=review_text, rating=rating)
        db.session.add(new_review)
        message = 'Review added successfully!'

    try:
        db.session.commit()
        return jsonify({'message': message})
    except Exception as e:
        return jsonify({'message': 'Error adding/updating review', 'error': str(e)}), 500

@app.route('/profile/<int:user_id>', methods=['GET'])
@token_required
def get_profile(current_user, user_id):
    try:
        if current_user.id != user_id:
            return jsonify({'message': 'Unauthorized'}), 403

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
def add_book(current_user):
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

@app.route('/mark_book_as_read', methods=['POST'])
@token_required
def mark_book_as_read(current_user):
    data = request.get_json()
    book_id = data.get('book_id')
    if not book_id:
        return jsonify({'message': 'Book ID is required'}), 400

    user_book = UserBook.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if not user_book:
        return jsonify({'message': 'Book not found in user library'}), 404

    try:
        user_book.read = True 
        db.session.commit()
        return jsonify({'message': 'Book marked as read successfully!'})
    except Exception as e:
        return jsonify({'message': 'Error marking book as read', 'error': str(e)}), 500


@app.route('/remove_book', methods=['POST'])
@token_required
def remove_book(current_user):
    data = request.get_json()
    if not data or 'action' not in data or data['action'] != 'delete':
        return jsonify({'message': 'Invalid action'}), 400

    book_id = data.get('book_id')
    if not book_id:
        return jsonify({'message': 'Book ID is required'}), 400

    user_book = UserBook.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if not user_book:
        return jsonify({'message': 'Book not found in user library'}), 404

    try:
        db.session.delete(user_book)
        db.session.commit()
        return jsonify({'message': 'Book removed from user library successfully!'})
    except Exception as e:
        app.logger.error(f'Error removing book from user library: {e}')
        return jsonify({'message': 'Error removing book from user library', 'error': str(e)}), 500


@app.route('/book_reviews/<int:book_id>', methods=['GET'])
@token_required
def get_book_reviews(current_user, book_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    reviews_query = Review.query.filter_by(book_id=book_id).join(User, Review.user_id == User.id)
    reviews_pagination = reviews_query.paginate(page=page, per_page=per_page, error_out=False)
    reviews = reviews_pagination.items
    review_list = [
        {'id': review.id, 'username': review.user.username, 'review': review.review, 'rating': review.rating}
        for review in reviews
    ]
    return jsonify({
        'reviews': review_list,
        'total_reviews': reviews_query.count(),
        'page': page,
        'pages': reviews_pagination.pages
    })

@app.route('/user_books/<int:user_id>', methods=['GET'])
@token_required
def get_user_books(current_user, user_id):
    if current_user.id != user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    try:
        books_to_read = UserBook.query.filter_by(user_id=user_id, read=False).join(Book).all()
        books_read = UserBook.query.filter_by(user_id=user_id, read=True).join(Book).all()

        books_to_read_output = [{
            'book_id': user_book.book.id,
            'title': user_book.book.title,
            'author': user_book.book.author,
            'image': user_book.book.image
        } for user_book in books_to_read]

        books_read_output = [{
            'book_id': user_book.book.id,
            'title': user_book.book.title,
            'author': user_book.book.author,
            'image': user_book.book.image
        } for user_book in books_read]

        return jsonify({
            'books_to_read': books_to_read_output,
            'books_read': books_read_output
        })
    except Exception as e:
        return jsonify({'message': 'Error fetching user books', 'error': str(e)}), 500

# Tratamento de Erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

# Inicialização do Logger
if __name__ == '__main__':
    import logging
    logging.basicConfig(filename='api.log', level=logging.INFO)
    app.run(host='0.0.0.0')
