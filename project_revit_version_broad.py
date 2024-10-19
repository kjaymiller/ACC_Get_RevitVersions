"""
THIS IS WHAT THE PROJECT DOES.

HOW TO USE THIS:

pass in the csv file as the only argument

`$ python project_revit_version_broad.py <CSV_PATH>`
"""

import sys
import os
import requests
import json
import datetime 
import csv
import dotenv

# Import configuration variables from the specified file

dotenv.load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET=os.getenv("CLIENT_SECRET")
HUB_ID=os.getenv("HUB_ID")
ACCESS_TOKEN = os.getenv("AUTODESK_ACCESS_TOKEN", None)

CSV_FILE_PATH= sys.argv[1]

# Global variable to store the access token and its expiration time
token_expiration_time = 0
TOKEN_EXPIRATION_BUFFER = 60  # Buffer time in seconds before token expiration
AUTODESK_API_BASE = "https://developer.api.autodesk.com"

def get_project_ids_from_csv(file_path:str) -> list[str]:
    with open(file_path) as csvfile:
        data = csv.DictReader(csvfile.read())
    return [f"b.{row['id']}" for row in data]  # Add "b." prefix to each ID

def validate_token(
        access_token: str | None,
        token_expiration_time: datetime.datetime, 
) -> bool:
    """Checks to see if the current API_TOKEN is valid"""
    return access_token and datetime.datetime.now() < token_expiration_time + datetime.timedelta(seconds=TOKEN_EXPIRATION_BUFFER)

def refresh_token() -> tuple[str, datetime.datetime]:
    """Generate a new token"""
    token_url = f"{AUTODESK_API_BASE}/authentication/v2/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "data:read data:write"  # Adjust scope according to your needs
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data['access_token']
    token_expiration_time = datetime.datetime.now() + token_data['expires_in']
    return access_token, token_expiration_time

session = requests.Session()
api_request = requests.Request(
    method="GET",
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    },
)
base_request = session.prepare_request(api_request)


def fetch_folder_contents(
        session: requests.Session,
        request:requests.PreparedRequest,
        project_id: str,
        folder_id: str,
) -> dict[str, str]:
    """Return the results from querying the api for the contents of the folder ID"""

    request.url = f"{AUTODESK_API_BASE}/data/v1/projects/{project_id}/folders/{folder_id}/contents"
    contents_response = session.send(request)
    contents_response.raise_for_status()
    return contents_response.json()


def is_folder(item: dict[str, str]):
    return item.get('type') == "folders"


def search_folders_recursively(folder_contents_response_data: dict[str, str|int]):

    for item in filter(is_folder, folder_contents_response_data):
        folder_name = item['attributes']['displayName']

        if 'Shared' not in folder_name: #Shared folders always contains "Shared"
            revit_data = search_folders_recursively(project_id, project_name, item['id'])
            if revit_data:
                return revit_data
        elif item['type'] == 'items' and 'attributes' in item and 'displayName' in item['attributes']:
            revit_data = extract_revit_data(project_id, project_name, folder_id)
            if revit_data:
                return revit_data

    return None


def fetch_revit_version_number(project_response_included_path: dict[str, str | int], target_version_number: int):
    """Checks a folders items for a revit_version_number matching the target_version_number"""
    for item in project_response_included_path:
        try:
            item["attributes"]["extension"]["data"]["revitProjectVersion"]

            if display_name.endswith('.rvt'):
                if 'included' in contents_data:
                    for included_item in contents_data['included']:
                        if 'attributes' in included_item and 'extension' in included_item['attributes']:
                            revit_version = included_item['attributes']['extension']['data'].get('revitProjectVersion')
                            if revit_version:
                                return {
                                    "Project ID": project_id,
                                    "Project name": project_name,
                                    "Revit file name": display_name,
                                    "Revit file ID": item_id,
                                    "Revit version": revit_version
                                }
        except KeyError:
            continue
    return None

def main():
    access_token = authenticate()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    all_revit_data = []

    # Get project IDs from the CSV file
    project_ids = get_project_ids_from_csv(CSV_FILE_PATH)

    for project_id in project_ids:  # Iterate over the specific Project IDs
        project_url = f'https://developer.api.autodesk.com/project/v1/hubs/{HUB_ID}/projects/{project_id}'
        project_response = requests.get(project_url, headers=headers)
        project_response.raise_for_status()
        project_data = project_response.json()
        project_name = project_data['data']['attributes']['name']
        
        root_folder_url = f'https://developer.api.autodesk.com/project/v1/hubs/{HUB_ID}/projects/{project_id}/topFolders'
        root_folder_response = requests.get(root_folder_url, headers=headers)
        root_folder_response.raise_for_status()
        root_folder_data = root_folder_response.json()

        revit_data = None
        for folder in root_folder_data['data']:
            if 'attributes' in folder and 'displayName' in folder['attributes'] and folder['attributes']['displayName'] == 'Project Files':
                revit_data = search_folders_recursively(project_id, project_name, folder['id'])
                if revit_data:
                    break  # Move on to the next project after finding the first Revit file

        if not revit_data:
            revit_data = {
                "Project ID": project_id,
                "Project name": project_name,
                "Revit file name": "",
                "Revit file ID": "",
                "Revit version": ""
            }

        all_revit_data.append(revit_data)
        print(f"Added to JSON: {revit_data}")  # Print the data being added

    # Export data to JSON file
    with open('revit_data.json', 'w') as json_file:
        json.dump(all_revit_data, json_file, indent=4)

if __name__ == "__main__":
    main()
