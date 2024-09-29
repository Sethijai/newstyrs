import os
import requests
import asyncio
from pymongo import MongoClient
from flask import Flask, jsonify
import backoff
from datetime import datetime

app = Flask(__name__)

# Get the database URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

# Connect to MongoDB
client = MongoClient(DATABASE_URL)
db = client.get_default_database()  # Replace with your database name if needed

# API Information
API_TOKEN = 'd81fc5d9c79ec9002ede6c03cddee0a4730ab826'
headers = {
    'Accept': 'application/json',
    'origintype': 'web',
    'token': API_TOKEN,
    'usertype': '2',
    'Content-Type': 'application/x-www-form-urlencoded'
}

# Function to get all subjects for a batch
@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_subject_details(batchId):
    subject_url = f"https://spec.iitschool.com/api/v1/batch-subject/{batchId}"
    response = requests.get(subject_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data["data"]["batch_subject"]
    else:
        print(f"Error getting subject details for batch {batchId}: {response.status_code}")
        return []

# Function to get live lecture links
@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_live_lecture_links(batchId, subjectId):
    live_url = f"https://spec.iitschool.com/api/v1/batch-detail/{batchId}?subjectId={subjectId}&topicId=live"
    response = requests.get(live_url, headers=headers)

    links = []
    if response.status_code == 200:
        data = response.json()
        classes = data["data"]["class_list"]["classes"]

        for lesson in classes:
            lesson_name = lesson["lessonName"]
            lesson_start_time = lesson["startDateTime"]
            lesson_id = lesson["id"]

            # Fetch class details for lessonUrl
            class_detail_url = f"https://spec.iitschool.com/api/v1/class-detail/{lesson_id}"
            class_response = requests.get(class_detail_url, headers=headers)

            if class_response.status_code == 200:
                class_data = class_response.json()
                lesson_url = class_data["data"]["class_detail"]["lessonUrl"]

                if lesson_url and any(c.isalpha() for c in lesson_url):
                    youtube_link = f"https://www.youtube.com/watch?v={lesson_url}"

                    # Save link to MongoDB
                    db.lecture_links.insert_one({
                        "link": youtube_link,
                        "start_time": lesson_start_time,
                        "lesson_name": lesson_name,
                        "date": datetime.now().strftime("%Y-%m-%d")
                    })
                    links.append({
                        "link": youtube_link,
                        "start_time": lesson_start_time,
                        "lesson_name": lesson_name
                    })

    return links

async def check_for_new_links(batch_ids):
    while True:
        for batchId in batch_ids:
            subjects = get_subject_details(batchId)
            for subject in subjects:
                subjectId = subject["id"]
                await get_live_lecture_links(batchId, subjectId)
        await asyncio.sleep(360)  # Check every 6 minutes

@app.route('/lectures/days', methods=['GET'])
def get_days():
    """Fetch all unique dates with saved lectures."""
    unique_dates = db.lecture_links.distinct("date")
    return jsonify(unique_dates)

@app.route('/lectures/<date>', methods=['GET'])
def get_lectures(date):
    """Fetch lectures saved for a specific date."""
    lectures = db.lecture_links.find({"date": date})
    return jsonify([{
        "lesson_name": lecture["lesson_name"],
        "link": lecture["link"],
        "start_time": lecture["start_time"]
    } for lecture in lectures])

if __name__ == "__main__":
    # Define your batch IDs
    batch_ids = [
        100,  # Example Batch ID
        99,
        # Add more batch IDs as needed
    ]
    # Start checking for new links
    asyncio.run(check_for_new_links(batch_ids))
    app.run(host='0.0.0.0', port=8080)
