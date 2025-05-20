# Veggie Quiz API

A FastAPI application for a quiz game with user authentication and quiz management.

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Create a `.env` file in the root directory
   - Add your database connection string and JWT secret:
     ```
     DATABASE_URL=postgresql://username:password@host:port/database_name
     SECRET_KEY=your-secure-secret-key-here  # Generate a secure random key
     ```
   - For generating a secure SECRET_KEY, you can use Python:
     ```python
     import secrets
     print(secrets.token_hex(32))  # This will generate a secure 64-character hex string
     ```

## Running the Application

Start the server with:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication

#### Create User
- **POST** `/users`
- **Description**: Create a new user account and get authentication token
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "username": "testuser"
  }
  ```
- **Response**:
  ```json
  {
    "id": 1,
    "email": "user@example.com",
    "username": "testuser",
    "created_at": "2024-05-01T12:00:00Z",
    "last_login": null,
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Notes**:
  - Returns user details and authentication token in a single response
  - Token is valid for 1 year
  - Returns 400 if email or username already exists
  - Returns 500 if database error occurs

#### Login
- **POST** `/token`
- **Description**: Get authentication token using email
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Note**: Token is valid for 1 year

#### Get Current User
- **GET** `/users/me`
- **Description**: Get details of currently authenticated user
- **Headers**: `Authorization: Bearer <token>`
- **Response**: User details

#### Delete Current User
- **DELETE** `/users/me`
- **Description**: Delete the currently authenticated user's account and all associated quiz results
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  ```json
  {
    "message": "User account deleted successfully"
  }
  ```
- **Notes**:
  - Requires authentication
  - Deletes all quiz results associated with the user
  - Cannot be undone
  - Returns 404 if user not found
  - Returns 500 if database error occurs

### Quizzes

#### Get Random Quizzes by Category
- **GET** `/quizzes/random-by-category`
- **Description**: Get 3 random quizzes from each category
- **Response**: Array of categories, each containing 3 random quizzes with their questions
- **Example Response**:
  ```json
  [
    {
      "category": "Geography",
      "quizzes": [
        {
          "id": 1,
          "name": "World Capitals",
          "description": "Test your knowledge of world capitals",
          "image": "https://example.com/image.jpg",
          "category": "Geography",
          "difficulty": "Easy",
          "created_at": "2024-05-01T12:00:00Z",
          "questions": [
            {
              "id": 1,
              "quiz_id": 1,
              "question_text": "What is the capital of France?",
              "choices": ["London", "Berlin", "Paris", "Madrid"],
              "correct_answer_index": 2,
              "explanation": "Paris is the capital of France",
              "category": "Geography",
              "difficulty": "Easy",
              "image": "https://example.com/paris.jpg"
            }
          ]
        }
        // ... 2 more random quizzes
      ]
    },
    {
      "category": "History",
      "quizzes": [
        // ... 3 random history quizzes
      ]
    }
  ]
  ```
- **Notes**:
  - Returns exactly 3 random quizzes per category
  - Only includes categories that have quizzes
  - Quizzes are randomly selected using PostgreSQL's RANDOM() function
  - Each quiz includes all its questions
  - Categories are ordered alphabetically

#### Get All Quizzes
- **GET** `/quizzes`
- **Description**: Get all available quizzes with their questions
- **Response**: Array of quizzes with their questions

#### Get Quiz Categories
- **GET** `/quiz-categories`
- **Description**: Get all unique quiz categories
- **Response**:
  ```json
  {
    "categories": ["Geography", "History", "Science"]
  }
  ```

#### Create Quiz
- **POST** `/quizzes`
- **Description**: Create a new quiz with questions
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "quiz": {
      "name": "Sample Quiz",
      "description": "A sample quiz",
      "image": "https://example.com/image.jpg",
      "category": "General",
      "difficulty": "Easy"
    },
    "questions": [
      {
        "question_text": "What is the capital of France?",
        "choices": ["London", "Berlin", "Paris", "Madrid"],
        "correct_answer_index": 2,
        "explanation": "Paris is the capital of France",
        "category": "Geography",
        "difficulty": "Easy",
        "image": "https://example.com/paris.jpg"
      }
    ]
  }
  ```
- **Response**: Created quiz with questions

#### Get Single Quiz
- **GET** `/quizzes/{quiz_id}`
- **Description**: Get a specific quiz by ID
- **Response**: Quiz details with questions

#### Delete Quiz
- **DELETE** `/quizzes/{quiz_id}`
- **Description**: Delete a quiz and its questions
- **Headers**: `Authorization: Bearer <token>`
- **Response**: Success message

### Quiz Results

#### Save Quiz Result
- **POST** `/quiz-results`
- **Description**: Save a user's quiz result
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "quiz_id": 1,
    "score": 85.5,
    "correct_answers": 8,
    "total_questions": 10
  }
  ```
- **Response**: Saved quiz result details

#### Get User's Quiz Results
- **GET** `/quiz-results`
- **Description**: Get all quiz results for the current user
- **Headers**: `Authorization: Bearer <token>`
- **Response**: Array of quiz results

## Data Models

### Quiz
```json
{
  "id": 1,
  "name": "Sample Quiz",
  "description": "A sample quiz",
  "image": "https://example.com/image.jpg",
  "category": "General",
  "difficulty": "Easy",
  "created_at": "2024-05-01T12:00:00Z",
  "questions": [
    {
      "id": 1,
      "question_text": "What is the capital of France?",
      "choices": ["London", "Berlin", "Paris", "Madrid"],
      "correct_answer_index": 2,
      "explanation": "Paris is the capital of France",
      "category": "Geography",
      "difficulty": "Easy",
      "image": "https://example.com/paris.jpg"
    }
  ]
}
```

### Quiz Result
```json
{
  "id": 1,
  "user_id": 1,
  "quiz_id": 1,
  "score": 85.5,
  "correct_answers": 8,
  "total_questions": 10,
  "created_at": "2024-05-01T12:30:00Z"
}
```

## Security Notes

1. Never commit your `.env` file to version control
2. Use HTTPS in production
3. Keep your SECRET_KEY secure and complex
4. Tokens are valid for 1 year - consider implementing token refresh if needed

## Error Handling

The API uses standard HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error

Error responses include a detail message explaining the error.