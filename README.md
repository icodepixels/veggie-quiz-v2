# FastAPI Success Message API

A simple FastAPI application that returns a success message and fetches user data from a PostgreSQL database.

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
   - Add your database connection string:
     ```
     DATABASE_URL=postgresql://username:password@host:port/database_name
     ```

## Running the Application

Start the server with:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

- `GET /`: Returns a success message
- `GET /users`: Returns all users from the database

## Security Note

Never commit your `.env` file to version control. Make sure to add it to your `.gitignore` file.

## Database Configuration

The application is configured to connect to a PostgreSQL database. Make sure to update the `DATABASE_URL` in `main.py` with your actual database credentials.