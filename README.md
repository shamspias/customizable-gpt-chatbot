# Dynamic AI Chatbot with Custom Training Sources
## Customizable-gpt-chatbot
This project is a dynamic AI chatbot that can be trained from various sources, such as PDFs, documents, websites, and YouTube videos. It uses a user system with social authentication through Google, and the Django REST framework for its backend. The chatbot leverages OpenAI's GPT-3.5 language model to conduct conversations and is designed for scalability and ease of use.

## Features
- Train chatbot from multiple sources (PDFs, documents, websites, YouTube videos)
- User system with social authentication through Google
- Connect with OpenAI GPT-3.5 language model for conversation
- Use Pinecone and FAISS for vector indexing
- Employ OpenAI's text-embedding-ada-002 for text embedding
- Python Langchain library for file processing and text conversion
- Scalable architecture with separate settings for local, staging, and production environments
- Dynamic site settings for title and prompt updates
- Multilingual support
- PostgreSQL database support
- Celery task scheduler with Redis and AWS SQS options
- AWS S3 bucket support for scalable hosting
- Easy deployment on Heroku or AWS

## Technologies
- Language: Python
- Framework: Django REST Framework
- Database: PostgreSQL

### Major Libraries:
- Celery
- Langchain 
- OpenAI
- Pinecone
- FAISS
## Requirements
- Python 3.8 or above
- Django 4.1 or above
- Pinecone API Key
- API key from OpenAI
- Redis or AWS SQS
- PostgreSQL database

## Future Scope
- Integration with more third-party services for authentication
- Support for additional file formats and media types for chatbot training
- Improved context-awareness in conversations
- Enhanced multilingual support with automatic language detection
- Integration with popular messaging platforms and chat applications

## How to run
- Clone the repository. `git clone https://github.com/shamspias/customizable-gpt-chatbot`
- Install the required packages by running `pip install -r requirements.txt`
- Run celery `celery -A config worker --loglevel=info`
- Run the command `python manage.py runserver`
- Open `http://127.0.0.1:8000/` in your browser

In linux and mac need to install 'sudo apt install python3-dev -y`
1. Make sure that you have the development libraries for libcurl installed on your system. You can install them by running the following command: `sudo apt-get install libcurl4-openssl-dev gcc libssl-dev -y`
2. Make sure that you have the latest version of pip and setuptools installed by running the following command: `pip install --upgrade pip setuptools`
3. `pip install pycurl`

## Deployment
The chatbot can be deployed on Heroku or AWS by following the standard procedures for Django deployment on these platforms.

## Issues
- If you don't use AWS SQS then no need to install `pycurl` and `boto3` packages.
- If you don't use AWS S3 then no need to install `django-storages` package.

## Note
Make sure that you have API key from OpenAI before running the project.

This is just a basic implementation of the project, you can always add more features and customization according to your requirement.

Enjoy!
