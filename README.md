# Dynamic AI Chatbot with Custom Training Sources
## Customizable-gpt-chatbot
This project is a dynamic AI chatbot that can be trained from various sources, such as PDFs, documents, websites, and YouTube videos. It uses a user system with social authentication through Google, and the Django REST framework for its backend. The chatbot leverages OpenAI's GPT-3.5 language model to conduct conversations and is designed for scalability and ease of use.

## Features
- Train chatbot from multiple sources (PDFs, documents, websites, YouTube videos)
- User system with social authentication through Google
- Connect with OpenAI GPT-3.5 Mistral and many more large language model for conversation
- Use Pinecone for vector indexing( Will add more)
- Employ OpenAI's Embedded models for text embedding
- Python Langchain library for file processing and text conversion
- Scalable architecture with separate settings for local, staging, and production environments
- Dynamic site settings for title and prompt updates
- Multilingual support
- MongoDB database support
- Celery task scheduler with Redis and AWS SQS options
- AWS S3 bucket support for scalable hosting
- Easy deployment on Heroku or AWS

## Technologies
- Language: Python
- Framework: FastAPI
- Database: MongoDB

### Major Libraries:
- Celery
- Langchain
- Langgraph

## Requirements
- Python 3.8 or above
- Pinecone API Key
- API key from OpenAI
- Mongo database

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


In linux and mac need to install 'sudo apt install python3-dev -y`
1. Make sure that you have the development libraries for libcurl installed on your system. You can install them by running the following command: `sudo apt-get install libcurl4-openssl-dev gcc libssl-dev -y`
2. Make sure that you have the latest version of pip and setuptools installed by running the following command: `pip install --upgrade pip setuptools`
3. `pip install pycurl`

## Deployment
The chatbot can be deployed on Heroku or AWS by following the standard procedures for Django deployment on these platforms.


## Note
Make sure that you have API key from OpenAI before running the project.

This is just a basic implementation of the project, you can always add more features and customization according to your requirement.

Enjoy!
