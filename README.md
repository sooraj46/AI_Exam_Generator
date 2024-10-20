# User Management System

This is a Flask-based User Management System with role-based access control, JWT authentication, and integrated Bootstrap styling.

## Features

- User Registration and Login
- Role-Based Access Control (Administrator, Exam Conductor, Exam Taker)
- Administrator Dashboard for Managing Users
- Exam Conductor Dashboard for Managing Groups
- Responsive Design with Bootstrap 5
- Deployment-ready with Google Cloud Platform (GCP) and PostgreSQL

## Setup Instructions

1. **Create a Virtual Environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables:**

   Create a `.env` file or set environment variables in your system for:

   - `SECRET_KEY`
   - `JWT_SECRET_KEY`
   - `DATABASE_URL`

   **Example `.env` file:**

   ```
   SECRET_KEY=your_secret_key
   JWT_SECRET_KEY=your_jwt_secret_key
   DATABASE_URL=postgresql://username:password@localhost:5432/your_db
   ```

4. **Initialize the Database:**

   Ensure that PostgreSQL is installed and a database is created as specified in `config.py`.

   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

5. **Run the Application:**

   ```bash
   python run.py
   ```

6. **Access the Application:**

   Open your web browser and navigate to `http://localhost:5000` to access the application.

## Deployment on GCP

Refer to the [Google Cloud Deployment Guide](#deployment-on-gcp) for detailed instructions on deploying the application to Google App Engine.

## License

This project is licensed under the MIT License.
