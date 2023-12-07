import csv
import json
import os
import requests
from datetime import date
from os.path import join
from time import sleep
from urllib.parse import urljoin

# base directory
base_directory = '/Users/susiehartings/Desktop'
data_directory = join(base_directory, 'data')

# set the endpoint
api_endpoint = 'https://www.loc.gov'
api_parameters = {'fo': 'json'}

# create directories if they don't exist
full_directory = join(data_directory, 'ftu_libs_metadata')
os.makedirs(full_directory, exist_ok=True)
print('Directory', full_directory, 'exists')


# handle API requests with retries
def make_api_request(url, params=None, retries=3):
    for _ in range(retries):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f'Request failed: {e}')
            sleep(1)  # Wait for a short time before retrying
    return None

# write CSV header
def write_csv_header(file_path, headers):
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

# extract image URL
def extract_image_url(item_data):
    try:
        resources = item_data.get('resources', [])
        for resource in resources:
            if isinstance(resource.get('image'), dict):
                return resource['image']['href']
            elif isinstance(resource.get('image'), str):
                return resource['image']

        print(f'No image found in resources for item_data: {item_data}')
        return 'Not found'
    except KeyError:
        print(f'Error extracting image from item_data: {item_data}')
        return 'Not found'


# process an item and write to CSV
def process_item(item, csv_writer, metadata_file_path):
    resource_id = item['link']
    short_id = resource_id.split('/')[2]

    # Make API request for item metadata
    item_metadata_url = f'{api_endpoint}/{item["link"].lstrip("/").rstrip("/")}{"?" if api_parameters else ""}{ "&".join(f"{key}={value}" for key, value in api_parameters.items())}'
    item_metadata_response = make_api_request(item_metadata_url)

    if item_metadata_response is None or item_metadata_response.status_code != 200:
        print(f'Failed to get metadata for {item_metadata_url}')
        return

    try:
        item_metadata_json = item_metadata_response.json()['item']
    except (json.JSONDecodeError, KeyError):
        print(f'Error decoding JSON for {item_metadata_url}')
        print(f'JSON response: {item_metadata_response.text}')  # Print the entire JSON response for debugging
        return

    # Write metadata to JSON file
    metadata_file = join(data_directory, 'ftu_libs_metadata', f'item_metadata-{short_id}.json')
    with open(metadata_file, 'w', encoding='utf-8') as json_file:
        json.dump(item_metadata_json, json_file)

    # Extract information for CSV
    item_id = item_metadata_json.get('library_of_congress_control_number', short_id)
    item_title = item_metadata_json.get('title', 'Not found')
    item_subject = item_metadata_json.get('subject', 'Not found')
    item_description = item_metadata_json.get('description', ['Not found'])[0]
    item_format = item_metadata_json.get('format', ['Not found'])[0]
    item_creator = item_metadata_json.get('names', 'Not found')
    item_rights = item_metadata_json.get('rights', 'Undetermined')
    item_language = item_metadata_json.get('language', 'Not found')
    item_digitized = item_metadata_json.get('digitized', 'Not found')

    # Extract image URL
    item_image_url = extract_image_url(item_metadata_json)

    # Write to CSV
    row_dict = {
        'title': item_title,
        'creator': item_creator,
        'date': date.today().strftime('%Y-%m-%d'),
        'description': item_description,
        'subject': item_subject,
        'format': item_format,
        'language': item_language,
        'digitized': item_digitized,
        'rights': item_rights,
        'image_url': item_image_url
    }

    csv_writer.writerow(row_dict)
    print(f'Added {item_id} to CSV')


headers = ['title', 'creator', 'date', 'description', 'subject', 'format', 'language', 'digitized', 'rights', 'image_url']
collection_info_csv = join(data_directory, 'collection_items_data.csv')

write_csv_header(collection_info_csv, headers)

collection_endpoint = 'https://www.loc.gov/free-to-use/'
collection_parameters = {'fo': 'json'}
collection_response = make_api_request(collection_endpoint, params=collection_parameters)

if collection_response is None or collection_response.status_code != 200:
    print(f'Failed to get collection list from {collection_endpoint}')
    exit()

collection_json = collection_response.json()

sample_item = collection_json['content']['set']['items'][0]
print(json.dumps(sample_item, indent=2))

with open(collection_info_csv, 'a', encoding='utf-8') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers)

    for item in collection_json['content']['set']['items']:
        if item['link'] == 'link' or '?' in item['link']:
            continue

        process_item(item, csv_writer, collection_info_csv)

print('\n--- LOG ---')
print(f'Wrote {collection_info_csv} with {len(collection_json["content"]["set"]["items"])} items')
