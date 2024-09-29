import requests
import os
import asyncio
from flask import Flask, render_template
from pymongo import MongoClient
from datetime import datetime
import backoff

# Flask app setup
app = Flask(__name__)

# MongoDB configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
client = MongoClient(DATABASE_URL)
db = client.IITSCHOOL  # Database name
lectures_collection = db.lectures  # Collection name

# API Information
API_TOKEN = 'd81fc5d9c79ec9002ede6c03cddee0a4730ab826'  # Replace with your actual API token
headers = {
    'Accept': 'application/json',
    'origintype': 'web',
    'token': API_TOKEN,
    'usertype': '2',
    'Content-Type': 'application/x-www-form-urlencoded'
}

# API URLs
subject_url = "https://spec.iitschool.com/api/v1/batch-subject/{batch_id}"
live_url = "https://spec.iitschool.com/api/v1/batch-detail/{batchId}?subjectId={subjectId}&topicId=live"

# Function to get subject details
@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_subject_details(batchId):
    formatted_url = subject_url.format(batch_id=batchId)
    response = requests.get(formatted_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data["data"]["batch_subject"]
    else:
        print(f"Error getting subject details: {response.status_code}")
        return []

# Function to get live lecture links
@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_live_lecture_links(batchId, subjectId):
    formatted_url = live_url.format(batchId=batchId, subjectId=subjectId)
    response = requests.get(formatted_url, headers=headers)

    links = []
    if response.status_code == 200:
        data = response.json()
        classes = data["data"]["class_list"]["classes"]

        for lesson in classes:
            lesson_name = lesson["lessonName"]
            lesson_start_time = lesson["startDateTime"]
            lesson_id = lesson["id"]

            # Save lecture to database
            lecture = {
                "lesson_name": lesson_name,
                "start_time": lesson_start_time,
                "subject_id": subjectId,
                "batch_id": batchId,
                "url": f"https://www.youtube.com/watch?v={lesson_id}"
            }
            lectures_collection.update_one({"url": lecture["url"]}, {"$setOnInsert": lecture}, upsert=True)

    return links

async def check_for_new_links(batch_ids):
    """Check for new lecture links every 6 minutes."""
    while True:
        for batchId in batch_ids:
            subjects = get_subject_details(batchId)
            for subject in subjects:
                subjectId = subject["id"]
                get_live_lecture_links(batchId, subjectId)
        await asyncio.sleep(360)  # Check every 6 minutes

@app.route('/')
def index():
    lectures = list(lectures_collection.find({}))
    return render_template('index.html', lectures=lectures)

if __name__ == "__main__":
    # Start checking for new links in a separate thread
    asyncio.run(check_for_new_links([100, 99, 119]))  # Add your batch IDs
    app.run(host='0.0.0.0', port=8080)
