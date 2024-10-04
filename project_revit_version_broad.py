import requests
import json
import time
import pandas as pd  # Import pandas to read the CSV file

# Import configuration variables from the specified file
from ..acc_refs.config import CLIENT_ID, CLIENT_SECRET, HUB_ID, CSV_FILE_PATH

# Global variable to store the access token and its expiration time
access_token = None
token_expiration_time = 0
TOKEN_EXPIRATION_BUFFER = 60  # Buffer time in seconds before token expiration

def get_project_ids_from_csv(file_path):
    df = pd.read_csv(file_path)
    project_ids = ["b." + str(id) for id in df.iloc[:, 0]]  # Add "b." prefix to each ID
    return project_ids

def authenticate():
    global access_token, token_expiration_time
    if access_token and time.time() < token_expiration_time - TOKEN_EXPIRATION_BUFFER:
        return access_token

    token_url = 'https://developer.api.autodesk.com/authentication/v2/token'
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials',
        'scope': 'data:read data:write'  # Adjust scope according to your needs
    }
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        print(f"Error authenticating: {response.status_code}, {response.text}")
        response.raise_for_status()
    token_data = response.json()
    access_token = token_data['access_token']
    token_expiration_time = time.time() + token_data['expires_in']
    return access_token

def fetch_folder_contents(project_id, folder_id):
    access_token = authenticate()
    contents_url = f'https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{folder_id}/contents'
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    contents_response = requests.get(contents_url, headers=headers)
    contents_response.raise_for_status()
    return contents_response.json()

def extract_revit_data(project_id, project_name, folder_id):
    contents_data = fetch_folder_contents(project_id, folder_id)

    for item in contents_data['data']:
        if 'attributes' in item and 'displayName' in item['attributes']:
            display_name = item['attributes']['displayName']
            item_id = item['id']
            
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
    return None

def search_folders_recursively(project_id, project_name, folder_id):
    contents_data = fetch_folder_contents(project_id, folder_id)

    for item in contents_data['data']:
        if item['type'] == 'folders' and 'attributes' in item and 'displayName' in item['attributes']:
            folder_name = item['attributes']['displayName']
            if 'Shared' not in folder_name:
                revit_data = search_folders_recursively(project_id, project_name, item['id'])
                if revit_data:
                    return revit_data
        elif item['type'] == 'items' and 'attributes' in item and 'displayName' in item['attributes']:
            revit_data = extract_revit_data(project_id, project_name, folder_id)
            if revit_data:
                return revit_data

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
TOKEN_EXPIRATION_BUFFER = 60  # Buffer time in seconds before token expiration