import os
import logging
import requests
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
db = SQLAlchemy(app)
migrate = Migrate(app, db)

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

User.user_books = db.relationship('UserBook', order_by=UserBook.id, back_populates='user')
Book.user_books = db.relationship('UserBook', order_by=UserBook.id, back_populates='book')

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
    books = Book.query.all()
    output = []
    for book in books:
        book_data = {
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'published_date': book.published_date,
            'isbn': book.isbn,
            'language': book.language
            'image' : book.image
            'pages' : book.pages
            'publisher' : book.publisher
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

@app.route('/add_book', methods=['POST'])
def add_book():
    data = request.get_json()
    isbn = data.get('isbn')
    user_id = data.get('user_id')

    if not isbn or not user_id:
        return jsonify({'message': 'ISBN and user ID are required'}), 400

    book = Book.query.filter_by(isbn=isbn).first()

    if not book:
        google_books_url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}'
        response = requests.get(google_books_url)
        book_data = response.json().get('items', [])

        if not book_data:
            return jsonify({'message': 'Book not found in Google Books API'}), 404

        book_info = book_data[0].get('volumeInfo', {})
        title = book_info.get('title', 'N/A')
        author = ', '.join(book_info.get('authors', []))
        language = book_info.get('language', 'N/A')
        image = book_info.get('imageLinks', {}).get('thumbnail')  # Obtendo o link da imagem da API do Google Books
        pages = book_info.get('pageCount')
        publisher = book_info.get('publisher')
        
        def format_published_date(published_date):
            try:
                return datetime.strptime(published_date, '%Y-%m-%d').date()
            except ValueError:
                return datetime.strptime(published_date, '%Y').date().replace(day=1, month=1)

        published_date = format_published_date(book_info.get('publishedDate', '1000'))

        book = Book(
            title=title,
            author=author,
            published_date=published_date,
            isbn=isbn,
            language=language,
            image=image,  # Armazenando o link da imagem na coluna 'image'
            pages=pages,  # Armazenando o número de páginas na coluna 'pages'
            publisher=publisher  # Armazenando o nome do editor na coluna 'publisher'
        )
        db.session.add(book)
        db.session.commit()

    user_book = UserBook.query.filter_by(user_id=user_id, book_id=book.id).first()
    if user_book:
        return jsonify({'message': 'Book already added to user library'}), 400

    user_book = UserBook(user_id=user_id, book_id=book.id)
    db.session.add(user_book)
    db.session.commit()

    return jsonify({'message': 'Book added to user library successfully!'})

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run()
