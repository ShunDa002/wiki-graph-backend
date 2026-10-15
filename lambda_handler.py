"""AWS Lambda entry point for the FastAPI ASGI application."""
from mangum import Mangum
from app import app

handler = Mangum(app, lifespan="auto")
