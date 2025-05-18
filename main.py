from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

logger.info(f"Attempting to connect to database with URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("Database connection successful")
except Exception as e:
    logger.error(f"Database connection failed: {str(e)}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 365  # 1 year in days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models for request/response
class QuestionBase(BaseModel):
    question_text: str
    choices: List[str]
    correct_answer_index: int
    explanation: str
    category: str
    difficulty: str
    image: str

class QuizBase(BaseModel):
    name: str
    description: str
    image: str
    category: str
    difficulty: str

class QuizCreate(BaseModel):
    quiz: QuizBase
    questions: List[QuestionBase]

class QuizResponse(BaseModel):
    id: int
    name: str
    description: str
    image: str
    category: str
    difficulty: str
    created_at: datetime
    questions: List[QuestionBase]

class QuizListResponse(BaseModel):
    id: int
    name: str
    description: str
    image: str
    category: str
    difficulty: str
    created_at: datetime
    questions: List[QuestionBase]

# Pydantic models for authentication
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    username: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime
    last_login: Optional[datetime] = None

class EmailLogin(BaseModel):
    email: str

class CategoryResponse(BaseModel):
    categories: List[str]

class QuizResultCreate(BaseModel):
    quiz_id: int
    score: float
    correct_answers: int
    total_questions: int

class QuizResultResponse(BaseModel):
    id: int
    user_id: int
    quiz_id: int
    score: float
    correct_answers: int
    total_questions: int
    created_at: datetime

class CategoryQuizzesResponse(BaseModel):
    category: str
    quizzes: List[QuizListResponse]

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=365)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    try:
        db = SessionLocal()
        user_query = text("SELECT * FROM users WHERE email = :email")
        result = db.execute(user_query, {"email": token_data.email})
        user = result.fetchone()
        if user is None:
            raise credentials_exception
        return UserResponse(
            id=user[0],
            email=user[1],
            username=user[2],
            created_at=user[3],
            last_login=user[4]
        )
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Success!"}


@app.post("/quizzes", response_model=QuizResponse)
async def create_quiz(quiz_data: QuizCreate):
    try:
        db = SessionLocal()
        # Start a transaction
        db.begin()

        try:
            # Insert quiz
            quiz_query = text("""
                INSERT INTO quiz (name, description, image, category, difficulty)
                VALUES (:name, :description, :image, :category, :difficulty)
                RETURNING id, name, description, image, category, difficulty, created_at
            """)
            quiz_params = {
                "name": quiz_data.quiz.name,
                "description": quiz_data.quiz.description,
                "image": quiz_data.quiz.image,
                "category": quiz_data.quiz.category,
                "difficulty": quiz_data.quiz.difficulty
            }
            logger.info(f"Inserting quiz with params: {quiz_params}")
            quiz_result = db.execute(quiz_query, quiz_params)
            quiz_row = quiz_result.fetchone()
            logger.info(f"Quiz insert result: {quiz_row}")

            # Create quiz dictionary with explicit type conversion
            quiz = {
                "id": int(quiz_row[0]),
                "name": str(quiz_row[1]),
                "description": str(quiz_row[2]),
                "image": str(quiz_row[3]),
                "category": str(quiz_row[4]),
                "difficulty": str(quiz_row[5]),
                "created_at": quiz_row[6]
            }
            logger.info(f"Quiz dict: {quiz}")

            # Insert questions
            questions = []
            for question in quiz_data.questions:
                # Convert choices to JSON string
                choices_json = json.dumps(question.choices)

                question_query = text("""
                    INSERT INTO questions (
                        quiz_id, question_text, choices, correct_answer_index,
                        explanation, category, difficulty, image
                    )
                    VALUES (
                        :quiz_id, :question_text, :choices, :correct_answer_index,
                        :explanation, :category, :difficulty, :image
                    )
                    RETURNING id, quiz_id, question_text, choices, correct_answer_index,
                             explanation, category, difficulty, image
                """)
                question_params = {
                    "quiz_id": quiz["id"],
                    "question_text": question.question_text,
                    "choices": choices_json,
                    "correct_answer_index": question.correct_answer_index,
                    "explanation": question.explanation,
                    "category": question.category,
                    "difficulty": question.difficulty,
                    "image": question.image
                }
                logger.info(f"Inserting question with params: {question_params}")
                question_result = db.execute(question_query, question_params)
                question_row = question_result.fetchone()
                logger.info(f"Question insert result: {question_row}")

                # Create question dictionary with explicit type conversion
                question_data = {
                    "id": int(question_row[0]),
                    "quiz_id": int(question_row[1]),
                    "question_text": str(question_row[2]),
                    "choices": question.choices,  # Use original choices
                    "correct_answer_index": int(question_row[4]),
                    "explanation": str(question_row[5]),
                    "category": str(question_row[6]),
                    "difficulty": str(question_row[7]),
                    "image": str(question_row[8])
                }
                logger.info(f"Question dict: {question_data}")
                questions.append(question_data)

            # Commit the transaction
            db.commit()

            # Return the created quiz with questions
            response = {**quiz, "questions": questions}
            logger.info(f"Returning response: {response}")
            return response

        except Exception as e:
            # Rollback the transaction in case of error
            db.rollback()
            logger.error(f"Error in transaction: {str(e)}")
            raise e

    except Exception as e:
        logger.error(f"Error creating quiz: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error creating quiz: {str(e)}"
        )
    finally:
        db.close()

@app.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int):
    try:
        db = SessionLocal()

        # Get quiz
        quiz_query = text("SELECT * FROM quiz WHERE id = :quiz_id")
        quiz_result = db.execute(quiz_query, {"quiz_id": quiz_id})
        quiz_row = quiz_result.fetchone()

        if not quiz_row:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Convert quiz row to dictionary
        quiz = {
            "id": int(quiz_row[0]),
            "name": str(quiz_row[1]),
            "description": str(quiz_row[2]),
            "image": str(quiz_row[3]),
            "category": str(quiz_row[4]),
            "difficulty": str(quiz_row[5]),
            "created_at": quiz_row[6]
        }

        # Get questions
        questions_query = text("""
            SELECT id, quiz_id, question_text, choices, correct_answer_index,
                   explanation, category, difficulty, image
            FROM questions WHERE quiz_id = :quiz_id
        """)
        questions_result = db.execute(questions_query, {"quiz_id": quiz_id})
        questions = []

        for row in questions_result:
            question_data = {
                "id": int(row[0]),
                "quiz_id": int(row[1]),
                "question_text": str(row[2]),
                "choices": row[3],  # This is already JSONB
                "correct_answer_index": int(row[4]),
                "explanation": str(row[5]),
                "category": str(row[6]),
                "difficulty": str(row[7]),
                "image": str(row[8])
            }
            questions.append(question_data)

        return {**quiz, "questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quiz: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching quiz: {str(e)}"
        )
    finally:
        db.close()

@app.delete("/quizzes/{quiz_id}")
async def delete_quiz(quiz_id: int):
    try:
        db = SessionLocal()

        # Delete quiz (cascade will handle questions)
        delete_query = text("DELETE FROM quiz WHERE id = :quiz_id")
        result = db.execute(delete_query, {"quiz_id": quiz_id})
        db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Quiz not found")

        return {"message": "Quiz deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quiz: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error deleting quiz: {str(e)}"
        )
    finally:
        db.close()

@app.get("/quizzes", response_model=List[QuizListResponse])
async def get_all_quizzes():
    try:
        db = SessionLocal()

        # Get all quizzes
        quizzes_query = text("SELECT * FROM quiz ORDER BY created_at DESC")
        quizzes_result = db.execute(quizzes_query)
        quizzes = []

        for quiz_row in quizzes_result:
            quiz = {
                "id": int(quiz_row[0]),
                "name": str(quiz_row[1]),
                "description": str(quiz_row[2]),
                "image": str(quiz_row[3]),
                "category": str(quiz_row[4]),
                "difficulty": str(quiz_row[5]),
                "created_at": quiz_row[6]
            }

            # Get questions for this quiz
            questions_query = text("""
                SELECT id, quiz_id, question_text, choices, correct_answer_index,
                       explanation, category, difficulty, image
                FROM questions WHERE quiz_id = :quiz_id
            """)
            questions_result = db.execute(questions_query, {"quiz_id": quiz["id"]})
            questions = []

            for question_row in questions_result:
                question_data = {
                    "id": int(question_row[0]),
                    "quiz_id": int(question_row[1]),
                    "question_text": str(question_row[2]),
                    "choices": question_row[3],  # This is already JSONB
                    "correct_answer_index": int(question_row[4]),
                    "explanation": str(question_row[5]),
                    "category": str(question_row[6]),
                    "difficulty": str(question_row[7]),
                    "image": str(question_row[8])
                }
                questions.append(question_data)

            quiz["questions"] = questions
            quizzes.append(quiz)

        return quizzes

    except Exception as e:
        logger.error(f"Error fetching quizzes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching quizzes: {str(e)}"
        )
    finally:
        db.close()

@app.get("/users", response_model=List[UserResponse])
async def get_users():
    try:
        db = SessionLocal()
        # Using text() for raw SQL query
        result = db.execute(text("SELECT * FROM users"))
        users = []
        for row in result:
            user = UserResponse(
                id=row[0],
                email=row[1],
                username=row[2],
                created_at=row[3],
                last_login=row[4]
            )
            users.append(user)
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching users: {str(e)}"
        )
    finally:
        db.close()

@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    try:
        db = SessionLocal()
        # Check if user already exists
        check_query = text("SELECT * FROM users WHERE email = :email OR username = :username")
        result = db.execute(check_query, {"email": user.email, "username": user.username})
        if result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or username already registered"
            )

        # Create new user
        insert_query = text("""
            INSERT INTO users (email, username)
            VALUES (:email, :username)
            RETURNING id, email, username, created_at, last_login
        """)
        result = db.execute(insert_query, {"email": user.email, "username": user.username})
        new_user = result.fetchone()
        db.commit()

        # Create access token
        access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        access_token = create_access_token(
            data={"sub": new_user[1]},  # new_user[1] is email
            expires_delta=access_token_expires
        )

        return {
            "id": new_user[0],
            "email": new_user[1],
            "username": new_user[2],
            "created_at": new_user[3],
            "last_login": new_user[4],
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error creating user: {str(e)}"
        )
    finally:
        db.close()

@app.post("/token", response_model=Token)
async def login_for_access_token(login_data: EmailLogin):
    try:
        db = SessionLocal()
        # Check if user exists
        user_query = text("SELECT * FROM users WHERE email = :email")
        result = db.execute(user_query, {"email": login_data.email})
        user = result.fetchone()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last login
        update_query = text("""
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = :user_id
            RETURNING last_login
        """)
        db.execute(update_query, {"user_id": user[0]})
        db.commit()

        # Create access token with 1 year expiration
        access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        access_token = create_access_token(
            data={"sub": user[1]},  # user[1] is email
            expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during login: {str(e)}"
        )
    finally:
        db.close()

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user

@app.delete("/users/me")
async def delete_user(current_user: UserResponse = Depends(get_current_user)):
    try:
        db = SessionLocal()

        # Delete user's quiz results first (due to foreign key constraint)
        delete_results_query = text("DELETE FROM quiz_results WHERE user_id = :user_id")
        db.execute(delete_results_query, {"user_id": current_user.id})

        # Delete user
        delete_user_query = text("DELETE FROM users WHERE id = :user_id")
        result = db.execute(delete_user_query, {"user_id": current_user.id})
        db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {"message": "User account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error deleting user: {str(e)}"
        )
    finally:
        db.close()

@app.get("/quiz-categories", response_model=CategoryResponse)
async def get_quiz_categories():
    try:
        db = SessionLocal()
        # Get all unique categories
        categories_query = text("SELECT DISTINCT category FROM quiz ORDER BY category")
        result = db.execute(categories_query)
        categories = [row[0] for row in result]
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching categories: {str(e)}"
        )
    finally:
        db.close()

@app.post("/quiz-results", response_model=QuizResultResponse)
async def save_quiz_result(
    result: QuizResultCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        db = SessionLocal()

        # Verify quiz exists
        quiz_query = text("SELECT id FROM quiz WHERE id = :quiz_id")
        quiz_result = db.execute(quiz_query, {"quiz_id": result.quiz_id})
        if not quiz_result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )

        # Check if user already has a result for this quiz
        existing_result_query = text("""
            SELECT id FROM quiz_results
            WHERE user_id = :user_id AND quiz_id = :quiz_id
        """)
        existing_result = db.execute(
            existing_result_query,
            {"user_id": current_user.id, "quiz_id": result.quiz_id}
        ).fetchone()

        if existing_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already completed this quiz"
            )

        # Insert new result
        insert_query = text("""
            INSERT INTO quiz_results (
                user_id, quiz_id, score, correct_answers, total_questions
            )
            VALUES (
                :user_id, :quiz_id, :score, :correct_answers, :total_questions
            )
            RETURNING id, user_id, quiz_id, score, correct_answers, total_questions, created_at
        """)

        result_data = {
            "user_id": current_user.id,
            "quiz_id": result.quiz_id,
            "score": result.score,
            "correct_answers": result.correct_answers,
            "total_questions": result.total_questions
        }

        new_result = db.execute(insert_query, result_data).fetchone()
        db.commit()

        return QuizResultResponse(
            id=new_result[0],
            user_id=new_result[1],
            quiz_id=new_result[2],
            score=new_result[3],
            correct_answers=new_result[4],
            total_questions=new_result[5],
            created_at=new_result[6]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving quiz result: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error saving quiz result: {str(e)}"
        )
    finally:
        db.close()

@app.get("/quiz-results", response_model=List[QuizResultResponse])
async def get_user_quiz_results(current_user: UserResponse = Depends(get_current_user)):
    try:
        db = SessionLocal()

        results_query = text("""
            SELECT id, user_id, quiz_id, score, correct_answers, total_questions, created_at
            FROM quiz_results
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """)

        results = db.execute(results_query, {"user_id": current_user.id})

        return [
            QuizResultResponse(
                id=row[0],
                user_id=row[1],
                quiz_id=row[2],
                score=row[3],
                correct_answers=row[4],
                total_questions=row[5],
                created_at=row[6]
            )
            for row in results
        ]

    except Exception as e:
        logger.error(f"Error fetching quiz results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error fetching quiz results: {str(e)}"
        )
    finally:
        db.close()

@app.get("/quizzes/random-by-category", response_model=List[CategoryQuizzesResponse])
async def get_random_quizzes_by_category():
    try:
        db = SessionLocal()

        # First get all categories
        categories_query = text("SELECT DISTINCT category FROM quiz ORDER BY category")
        categories_result = db.execute(categories_query)
        categories = [row[0] for row in categories_result]

        response = []

        for category in categories:
            # Get 3 random quizzes for each category
            quizzes_query = text("""
                SELECT q.*,
                       json_agg(
                           json_build_object(
                               'id', qu.id,
                               'quiz_id', qu.quiz_id,
                               'question_text', qu.question_text,
                               'choices', qu.choices,
                               'correct_answer_index', qu.correct_answer_index,
                               'explanation', qu.explanation,
                               'category', qu.category,
                               'difficulty', qu.difficulty,
                               'image', qu.image
                           )
                       ) as questions
                FROM quiz q
                LEFT JOIN questions qu ON q.id = qu.quiz_id
                WHERE q.category = :category
                GROUP BY q.id
                ORDER BY RANDOM()
                LIMIT 3
            """)

            quizzes_result = db.execute(quizzes_query, {"category": category})
            quizzes = []

            for quiz_row in quizzes_result:
                quiz = {
                    "id": int(quiz_row[0]),
                    "name": str(quiz_row[1]),
                    "description": str(quiz_row[2]),
                    "image": str(quiz_row[3]),
                    "category": str(quiz_row[4]),
                    "difficulty": str(quiz_row[5]),
                    "created_at": quiz_row[6],
                    "questions": quiz_row[7] if quiz_row[7] != [None] else []
                }
                quizzes.append(quiz)

            if quizzes:  # Only add categories that have quizzes
                response.append({
                    "category": category,
                    "quizzes": quizzes
                })

        return response

    except Exception as e:
        logger.error(f"Error fetching random quizzes by category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching random quizzes: {str(e)}"
        )
    finally:
        db.close()




