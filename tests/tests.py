import os
import unittest
from dotenv import load_dotenv
from api.index import app, db, User, Book, Review, UserBook
from werkzeug.security import generate_password_hash

load_dotenv()

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        self.create_test_user()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        if os.path.exists('test.db'):
            os.remove('test.db')

    def create_test_user(self):
        hashed_password = generate_password_hash('test', method='pbkdf2:sha256')
        test_user = User(username='test', password=hashed_password)
        db.session.add(test_user)
        db.session.commit()

    def test_register(self):
        # Teste de registro de usuário
        response = self.app.post('/register', json={'username': 'testuser', 'password': 'testpass'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Registered successfully!', response.get_json()['message'])

    def test_login(self):
        # Teste de login de usuário
        response = self.app.post('/login', json={'username': 'test', 'password': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Logged in successfully!', response.get_json()['message'])

    def test_get_books(self):
        # Teste de obtenção de livros
        response = self.app.get('/books')
        self.assertEqual(response.status_code, 200)

    def test_get_book(self):
        # Teste de obtenção de um livro específico
        test_book = Book(title='Test Book', author='Test Author', isbn='1234567890123')
        self.db.session.add(test_book)
        self.db.session.commit()

        response = self.app.get(f'/book/{test_book.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['book']['title'], 'Test Book')

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
