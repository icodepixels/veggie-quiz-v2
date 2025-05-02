from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

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

@app.get("/")
async def root():
    return {"message": "Success!"}

@app.get("/users")
async def get_users():
    try:
        db = SessionLocal()
        # Using text() for raw SQL query
        result = db.execute(text("SELECT * FROM users"))
        print("users result: ", result)
        users = [dict(row) for row in result]
        db.close()
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching users: {str(e)}"
        )

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
        quiz = dict(quiz_result.fetchone())

        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Get questions
        questions_query = text("""
            SELECT id, quiz_id, question_text, choices, correct_answer_index,
                   explanation, category, difficulty, image
            FROM questions WHERE quiz_id = :quiz_id
        """)
        questions_result = db.execute(questions_query, {"quiz_id": quiz_id})
        questions = []
        for row in questions_result:
            question_data = dict(row)
            # Convert choices from JSONB to list
            question_data["choices"] = question_data["choices"]
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

