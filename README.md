# Hemanta's Box Office

A simple ticketing system that lets you hold seats temporarily and then book them. Built with Django, Redis, and Celery.

## What This Does

- Create events with a certain number of seats
- Hold seats for a few minutes (they expire automatically)
- Book seats from active holds
- No overbooking - the system prevents it
- Get real-time metrics and stats


### Core Stuff (Features)
- Create events with total seat count
- Hold seats for 2 minutes (configurable)
- Book seats from active holds
- Automatic hold expiry
- No overbooking protection
- Partial fulfillment (if you ask for 5 seats but only 3 are available, you get 3)
- Real-time metrics endpoint
- Structured logging with request tracking
- Custom hold expiry time (1-10 minutes)
- API documentation with Swagger
- Docker support for easy setup

## Quick Start

### Using Docker (Easiest)

```bash
# Clone the repo
git clone <your-repo-url>
cd pibiT

# Start everything
docker-compose up --build -d

# Check if it's working
curl http://localhost:8000/api/events/
```

### Local Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Redis (you need this)
brew install redis  # on macOS
# sudo apt-get install redis-server  # on Ubuntu

# Copy environment file
cp env_example.txt .env

# Run database setup
python manage.py migrate

# Create admin user
python set_admin_password.py

# Start Redis
redis-server

# Start Django
python manage.py runserver

# Start Celery (in another terminal)
celery -A ticketing_service worker --loglevel=info --beat --concurrency=1
```


## Tech Stack

- **Backend**: Django 4.2 + Django REST Framework
- **Database**: SQLite3
- **Cache/Queue**: Redis 7.x
- **Background Tasks**: Celery
- **Documentation**: Swagger/OpenAPI
- **Containerization**: Docker + Docker Compose


## Project Structure

```
pibiT/
├── boxoffice/           # Main Django app
│   ├── models.py       # Database models
│   ├── views.py        # API endpoints
│   ├── serializers.py  # Data serialization
│   ├── tasks.py        # Background tasks
│   └── utils.py        # Helper functions
├── ticketing_service/  # Django project
├── docker-compose.yml  # Docker setup
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

---

Built for the Pibit.ai Backend Engineer assignment! 🎪