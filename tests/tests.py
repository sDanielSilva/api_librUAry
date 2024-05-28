import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from api.index import app, db, User, Book, Review, UserBook
from werkzeug.security import generate_password_hash


class TestAPI(unittest.TestCase):
    def setUp(self):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db' //linnk para a nossa bd
        self.app = app.test_client()
        self.db = db
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()

    def test_register(self):
        response = self.app.post('/register', json={'username': 'test', 'password': 'test'})
        self.assertEqual(response.status_code, 200)

    def test_login(self):
        hashed_password = generate_password_hash('test', method='pbkdf2:sha256')
        test_user = User(username='test', password=hashed_password)
        self.db.session.add(test_user)
        self.db.session.commit()

        response = self.app.post('/login', json={'username': 'test', 'password': 'test'})
        self.assertEqual(response.status_code, 200)

    def test_get_books(self):
        response = self.app.get('/books')
        self.assertEqual(response.status_code, 200)

    def test_get_book(self):
        test_book = Book(title='Test Book', author='Test Author', isbn='1234567890123')
        self.db.session.add(test_book)
        self.db.session.commit()

        response = self.app.get(f'/book/{test_book.id}')
        self.assertEqual(response.status_code, 200)

    def test_add_review(self):
        test_user = User.query.filter_by(username='test').first()
        test_book = Book.query.filter_by(isbn='1234567890123').first()

        response = self.app.post('/review', json={'book_id': test_book.id, 'user_id': test_user.id, 'review_text': 'Great book!', 'rating': 5})
        self.assertEqual(response.status_code, 200)

    def test_get_profile(self):
        test_user = User.query.filter_by(username='test').first()

        response = self.app.get(f'/profile/{test_user.id}')
        self.assertEqual(response.status_code, 200)

    def test_add_book(self):
        test_user = User.query.filter_by(username='test').first()
        response = self.app.post('/add_book', json={'isbn': '1234567890123', 'user_id': test_user.id})
        self.assertEqual(response.status_code, 200)

    def test_get_book_reviews(self):
        test_book = Book.query.filter_by(isbn='1234567890123').first()
        response = self.app.get(f'/book_reviews/{test_book.isbn}')
        self.assertEqual(response.status_code, 200)

    def test_get_user_books(self):
        test_user = User.query.filter_by(username='test').first()
        response = self.app.get(f'/user_books/{test_user.id}')
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
