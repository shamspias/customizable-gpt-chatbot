# 🤖 Customizable GPT Chatbot

A powerful, AI-powered chatbot you can train using **PDFs, documents, websites, and YouTube videos** — all in one platform!

---

## 🧠 What This Project Does

This is a **dynamic AI chatbot** built with Python and Django. It uses **OpenAI’s GPT-3.5** to have smart conversations, and you can train it with your own content (like PDFs, websites, and more). It also supports **Google login** and is built to scale across different environments (local, staging, production).

---

## 🚀 Features

* ✅ Train your chatbot using:

  * PDFs
  * Word/Doc files
  * Websites (URLs)
  * YouTube videos
* 🔐 Google Login (social authentication)
* 🧠 Conversations powered by **OpenAI GPT-3.5**
* 🔍 Uses **Pinecone** and **FAISS** to quickly search through your training data
* 📦 Supports file processing using the **LangChain** library
* 🌍 Multilingual support
* ☁️ Deployable to **Heroku** or **AWS**
* 🗃️ Uses **PostgreSQL** as the database
* 🔄 Task handling with **Celery**, and supports **Redis** or **AWS SQS**
* 📂 File storage on **AWS S3**

---

## 🛠️ Technologies Used

* **Language**: Python
* **Backend Framework**: Django REST Framework
* **Database**: PostgreSQL
* **Key Libraries**:

  * OpenAI API
  * Pinecone
  * FAISS
  * Celery
  * LangChain

---

## 📦 Requirements

Before starting, make sure you have:

* Python 3.8+
* Django 4.1+
* API Keys for:

  * **OpenAI**
  * **Pinecone**
* Redis or AWS SQS (for background tasks)
* PostgreSQL
* Optional: AWS S3 (for cloud storage)

---

## 🖥️ How to Run Locally (Beginner Version)

1. **Clone the project**

   ```bash
   git clone https://github.com/shamspias/customizable-gpt-chatbot
   cd customizable-gpt-chatbot
   ```

2. **Install dependencies**

   ```bash
   pip install --upgrade pip setuptools
   pip install -r requirements.txt
   ```

3. **Install system packages (Linux/macOS only)**

   ```bash
   sudo apt install python3-dev libcurl4-openssl-dev gcc libssl-dev -y
   pip install pycurl
   ```

4. **Start background worker (Celery)**

   ```bash
   celery -A config worker --loglevel=info
   ```

5. **Run the server**

   ```bash
   python manage.py runserver
   ```

6. **Visit in your browser**:
   [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## ☁️ Deployment

You can deploy the chatbot easily to:

* **Heroku**
* **AWS (Elastic Beanstalk, EC2, etc.)**

Follow standard Django deployment steps.

---

## 🧩 Notes & Tips

* **No AWS SQS?**
  → You don’t need to install `pycurl` or `boto3`.

* **No AWS S3?**
  → You don’t need to install `django-storages`.

* **Don’t forget your API keys!**

  * You must have a working **OpenAI API Key** before running the chatbot.

---

## 🔮 Future Improvements (Planned)

* More authentication options (e.g. GitHub, Microsoft)
* Support for more file types and video formats
* Smarter, more contextual chat replies
* Auto-detect user language
* Integrations with apps like WhatsApp, Telegram, or Slack

---

## ✅ You're All Set!

Feel free to customize and build on this project to fit your needs.
Have fun building your own smart chatbot! 🤖💬
