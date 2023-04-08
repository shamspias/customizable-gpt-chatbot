# Customizable-gpt3-chatbot
A Django-based intelligent chatbot with customizable learning and multi-language support using GPT-3. The chatbot is able to learn from books, articles, and other information provided by the user. Additionally, the chatbot is able to work with multiple languages.

## Features
- Customizable learning capabilities with GPT-3
- Multi-language support
- Natural Language Processing (NLP) using NLTK/spaCy/GPT-3 
- Conversational speech with OpenAI whisper
- User-friendly interface
- Social Authentication System
- Track Record of every conversation for specific users
- Give answer based on last 15 conversations
- Easy deployment on Heroku or AWS

## Technologies
- Django & Django Rest Framework
- Celery
- Hugging Face's transformers library
- Embedding Model
- Vector Database
- OpenAI GPT-3 & Whisper

## Requirements
- Python 3.8 or above
- Django 3.2 or above
- Hugging Face's transformers library
- Pinecone API Key
- API key from OpenAI

## How to run
- Clone the repository.
- Install the required packages by running `pip install -r requirements.txt`
- Run celery `celery -A config worker --loglevel=info`
- Run the command `python manage.py runserver`
- Open `http://127.0.0.1:8000/` in your browser

In linux need to install `pycurl`
1. Make sure that you have the development libraries for libcurl installed on your system. You can install them by running the following command: `sudo apt-get install libcurl4-openssl-dev gcc -y`
2. Make sure that you have the latest version of pip and setuptools installed by running the following command: `pip install --upgrade pip setuptools`
3. `pip install pycurl`

## Deployment
The chatbot can be deployed on Heroku or AWS by following the standard procedures for Django deployment on these platforms.

## Note
Make sure that you have API key from OpenAI before running the project.

This is just a basic implementation of the project, you can always add more features and customization according to your requirement.

Enjoy!
