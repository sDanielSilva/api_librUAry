import os
import datetime
from functools import wraps
import jwt
import requests
from flask import Flask, request, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.extensions import AsIs
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

conn = psycopg2.connect(
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASS'),
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT')
)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token')
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (data['user_id'],))
                current_user = cur.fetchone()
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(current_user, *args, **kwargs)
    return decorated


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
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])

        exp_date = datetime.datetime.fromtimestamp(decoded_token['exp'], tz=datetime.timezone.utc)
        
        if exp_date < datetime.datetime.now(datetime.timezone.utc):
            return jsonify({'is_valid': False, 'message': 'Token has expired'}), 401
        
        return jsonify({'is_valid': True, 'message': 'Token is valid'})
    except jwt.ExpiredSignatureError:
        return jsonify({'is_valid': False, 'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
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

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

    if existing_user:
        return jsonify({'message': 'Username already exists'}), 400

    try:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, pgp_sym_encrypt(%s, %s))", (username, hashed_password, app.config['SECRET_KEY']))
        conn.commit()
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

    with conn.cursor() as cur:
        cur.execute("SELECT username, pgp_sym_decrypt(password::bytea, %s) as password FROM users WHERE username = %s", (app.config['SECRET_KEY'], username))
        user = cur.fetchone()
    
    if not user or not check_password_hash(user['password'].decode(), password):
        return jsonify({'message': 'Login failed!'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'message': 'Logged in successfully!', 'token': token, 'user_id': user['id']})

@app.route('/books', methods=['GET'])
def get_books():
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM books")
            books = cur.fetchall()
            output = [{
                'id': book['id'],
                'title': book['title'],
                'author': book['author'],
                'published_date': book['published_date'],
                'isbn': book['isbn'],
                'language': book['language'],
                'image': book['image'],
                'pages': book['pages'],
                'publisher': book['publisher']
            } for book in books]
            return jsonify({'books': output})
    except Exception as e:
        return jsonify({'message': 'Error fetching books', 'error': str(e)}), 500

@app.route('/book/<int:book_id>', methods=['GET'])
def get_book(book_id):
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM books WHERE id = %s", (book_id,))
            book = cur.fetchone()
        if book is None:
            return jsonify({'message': 'Book not found'}), 404

        output = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'published_date': book['published_date'],
            'isbn': book['isbn'],
            'language': book['language'],
            'image': book['image'],
            'pages': book['pages'],
            'publisher': book['publisher']
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

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM reviews WHERE book_id = %s AND user_id = %s", (book_id, current_user['id']))
        existing_review = cur.fetchone()

    if existing_review:
        with conn.cursor() as cur:
            cur.execute("UPDATE reviews SET review = %s, rating = %s WHERE id = %s", (review_text, rating, existing_review['id']))
        message = 'Review updated successfully!'
    else:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO reviews (book_id, user_id, review, rating) VALUES (%s, %s, %s, %s)", (book_id, current_user['id'], review_text, rating))
        message = 'Review added successfully!'

    try:
        conn.commit()
        return jsonify({'message': message})
    except Exception as e:
        return jsonify({'message': 'Error adding/updating review', 'error': str(e)}), 500


@app.route('/profile/<int:user_id>', methods=['GET'])
@token_required
def get_profile(current_user, user_id):
    try:
        if current_user['id'] != user_id:
            return jsonify({'message': 'Unauthorized'}), 403

        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()

        if not user:
            return jsonify({'message': 'User not found'}), 404

        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM reviews WHERE user_id = %s", (user_id,))
            reviews = cur.fetchall()

        review_list = [{'book_id': review['book_id'], 'review': review['review'], 'rating': review['rating']} for review in reviews]
        return jsonify({'username': user['username'], 'reviews': review_list})
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

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT * FROM books WHERE isbn = %s", (isbn,))
        book = cur.fetchone()

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

            with conn.cursor() as cur:
                cur.execute("INSERT INTO books (title, author, published_date, isbn, language, image, pages, publisher) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (title, author, published_date, isbn, language, image, pages, publisher))
                book_id = cur.fetchone()[0]
            conn.commit()
        except requests.exceptions.RequestException as e:
            app.logger.error(f'Error fetching book data from Google Books API: {e}')
            return jsonify({'message': 'Error fetching book data from Google Books API', 'error': str(e)}), 500

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_books WHERE user_id = %s AND book_id = %s", (user_id, book_id))
        user_book = cur.fetchone()

    if user_book:
        return jsonify({'message': 'Book already added to user library'}), 400

    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_books (user_id, book_id) VALUES (%s, %s)", (user_id, book_id))
        conn.commit()
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

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_books WHERE user_id = %s AND book_id = %s", (current_user['id'], book_id))
        user_book = cur.fetchone()

    if not user_book:
        return jsonify({'message': 'Book not found in user library'}), 404

    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_books SET read = TRUE WHERE id = %s", (user_book['id'],))
        conn.commit()
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

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_books WHERE user_id = %s AND book_id = %s", (current_user['id'], book_id))
        user_book = cur.fetchone()

    if not user_book:
        return jsonify({'message': 'Book not found in user library'}), 404

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_books WHERE id = %s", (user_book['id'],))
        conn.commit()
        return jsonify({'message': 'Book removed from user library successfully!'})
    except Exception as e:
        app.logger.error(f'Error removing book from user library: {e}')
        return jsonify({'message': 'Error removing book from user library', 'error': str(e)}), 500

@app.route('/book_reviews/<int:book_id>', methods=['GET'])
@token_required
def get_book_reviews(current_user, book_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT * FROM reviews WHERE book_id = %s ORDER BY id LIMIT %s OFFSET %s", (book_id, per_page, (page - 1) * per_page))
        reviews = cur.fetchall()
    review_list = [{'id': review['id'], 'username': review['username'], 'review': review['review'], 'rating': review['rating'], 'user_id': review['user_id']} for review in reviews]
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM reviews WHERE book_id = %s", (book_id,))
        total_reviews = cur.fetchone()[0]
    return jsonify({
        'reviews': review_list,
        'total_reviews': total_reviews,
        'page': page,
        'pages': (total_reviews // per_page) + (total_reviews % per_page > 0)
    })

@app.route('/user_books/<int:user_id>', methods=['GET'])
@token_required
def get_user_books(current_user, user_id):
    if current_user['id'] != user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM user_books JOIN books ON user_books.book_id = books.id WHERE user_id = %s AND read = FALSE", (user_id,))
            books_to_read = cur.fetchall()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM user_books JOIN books ON user_books.book_id = books.id WHERE user_id = %s AND read = TRUE", (user_id,))
            books_read = cur.fetchall()

        books_to_read_output = [{
            'book_id': user_book['book_id'],
            'title': user_book['title'],
            'author': user_book['author'],
            'image': user_book['image']
        } for user_book in books_to_read]

        books_read_output = [{
            'book_id': user_book['book_id'],
            'title': user_book['title'],
            'author': user_book['author'],
            'image': user_book['image']
        } for user_book in books_read]

        return jsonify({
            'books_to_read': books_to_read_output,
            'books_read': books_read_output
        })
    except Exception as e:
        return jsonify({'message': 'Error fetching user books', 'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    import logging
    logging.basicConfig(filename='api.log', level=logging.INFO)
    app.run(host='0.0.0.0')
