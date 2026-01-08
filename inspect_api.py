import requests
import re
import json

BASE_API_URL = "https://ec.europa.eu/info/law/better-regulation"

def get_publication_id(initiative_id):
    api_url = f"{BASE_API_URL}/brpapi/groupInitiatives/{initiative_id}"
    print(f"Fetching initiative details from {api_url}")
    r = requests.get(api_url)
    data = r.json()
    
    # Just print the publications to see what we have
    best_pub = None
    max_feedback = -1
    
    if 'publications' in data:
        for pub in data['publications']:
            tf = pub.get('totalFeedback', 0)
            if tf > max_feedback:
                max_feedback = tf
                best_pub = pub
    
    if best_pub:
        return best_pub['id']
    return None

def test_download(document_id):
    url = f"{BASE_API_URL}/api/download/{document_id}"
    print(f"Testing download from {url}")
    r = requests.get(url, stream=True)
    print(f"Status Code: {r.status_code}")
    print(f"Content Type: {r.headers.get('Content-Type')}")
    if r.status_code == 200:
        print("Download URL is valid.")
    else:
        print("Download URL failed.")

def main():
    # ... existing main code ...
    # hardcode test for now
    test_download("090166e525b9306c")


if __name__ == "__main__":
    main()
