#!/usr/bin/env python3

import argparse
import pickle
import sys
import pprint
import os

from pathlib import Path

import googleapiclient.http
import googleapiclient.errors

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

OAUTH2_SCOPE = ['https://www.googleapis.com/auth/drive']
CLIENT_SECRETS = 'client_secrets.json'


def get_dev_creds(client_secrets, scopes):
    """Used saved authentication token (only in devmode)."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if Path('token.pickle').is_file():
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                client_secrets,
                scopes,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob',
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f'\nUse this link for authorization: {auth_url}')
            code = input('\nAuth. code: ').strip()
            flow.fetch_token(code=code)
            creds = flow.credentials

        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_creds(client_secrets, scopes):
    """Ask the user for an authentication token."""
    flow = Flow.from_client_secrets_file(
        client_secrets,
        scopes,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    print(f'\nUse this link for authorization: {auth_url}')
    code = input('\nAuth. code: ').strip()
    flow.fetch_token(code=code)
    creds = flow.credentials
    return creds

def get_drive_service(credentials):
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

def get_permission_id_for_email(service, email):
    try:
        id_resp = service.permissions().getIdForEmail(email=email).execute()
        return id_resp['id']
    except googleapiclient.errors.HttpError as e:
        print(f'An error occured: {e}')

def show_info(service, drive_item, prefix, permission_id):
    try:
        print(os.path.join(prefix, drive_item['title']))
        print(f'Would set new owner to {permission_id}.')
    except KeyError:
        print('No title for this item:')
        pprint.pprint(drive_item)

def grant_ownership(service, drive_item, prefix, permission_id, show_already_owned):
    full_path = os.path.join(os.path.sep.join(prefix), drive_item['title'])
    #pprint.pprint(drive_item)

    current_user_owns = False
    for owner in drive_item['owners']:
        if owner['permissionId'] == permission_id:
            if show_already_owned:
                print(f'Ownership already correct for "{full_path}".')
            return
        elif owner['isAuthenticatedUser']:
            current_user_owns = True

    print(f'Changing ownership for "{full_path}"... ', end='', flush=True)

    if not current_user_owns:
        print('Skipped: not owned by current user.')
        return

    try:
        permission = service.permissions().get(fileId=drive_item['id'], permissionId=permission_id).execute()
        permission['role'] = 'owner'
        result = service.permissions().update(fileId=drive_item['id'], permissionId=permission_id, body=permission, transferOwnership=True).execute()
        print('Done.')
        if len(prefix) < 1:
            # Top level folder is changed last. Exit script to avoid additional
            #   "My Drive" trawling.
            exit()
        return result
    except googleapiclient.errors.HttpError as e:
        if e.resp.status != 404:
            print(f'Error: {e}')
            return
        else:
            print("Server error 404.")

    print('    Creating new ownership permissions.')
    permission = {'role': 'owner',
                  'type': 'user',
                  'id': permission_id}
    try:
        service.permissions().insert(fileId=drive_item['id'], body=permission, emailMessage='Automated recursive transfer of ownership.').execute()
    except googleapiclient.errors.HttpError as e:
        print(f'An error occurred inserting ownership permissions: {e}')

def process_all_files(service, callback=None, callback_args=None, minimum_prefix=None, current_prefix=None, folder_id='root'):
    if minimum_prefix is None:
        minimum_prefix = []
    if current_prefix is None:
        current_prefix = []
    if callback_args is None:
        callback_args = []

    print(f'Gathering file listings for prefix {current_prefix}...')

    page_token = None
    while True:
        try:
            param = {}
            if page_token:
                param['pageToken'] = page_token
            children = service.children().list(folderId=folder_id, **param).execute()
            for child in children.get('items', []):
                item = service.files().get(fileId=child['id']).execute()
                #pprint.pprint(item)
                if folder_id == 'root' and item['title'] != minimum_prefix[0]:
                    # Skip irrelevant files and folders in "My Drive".
                    # print(f"Skipping \"{item['title']}\"")
                    continue
                if item['kind'] == 'drive#file':
                    if current_prefix[:len(minimum_prefix)] == minimum_prefix:
                        # print(f"File: \"{item['title']}\" ({current_prefix}, {item['id']})")
                        callback(service, item, current_prefix, **callback_args)
                    if item['mimeType'] == 'application/vnd.google-apps.folder':
                        # print(f"Folder: \"{item['title']}\" ({current_prefix}, {item['id']})")
                        next_prefix = current_prefix + [item['title']]
                        comparison_length = min(len(next_prefix), len(minimum_prefix))
                        if minimum_prefix[:comparison_length] == next_prefix[:comparison_length]:
                            process_all_files(service, callback, callback_args, minimum_prefix, next_prefix, item['id'])
                            callback(service, item, current_prefix, **callback_args)

            page_token = children.get('nextPageToken')
            if not page_token:
                break
        except googleapiclient.errors.HttpError as e:
            print(f'An error occurred: {e}')
            break

def get_drive_search_results(service, query, page_token=None):
    """Get results of search query on specified account."""
    results = []
    while True:
        try:
            response = service.files().list(
                q=query,
                spaces='drive',
                supportsAllDrives=True,
                fields='nextPageToken, files(id, name, modifiedTime, owners, parents)', #fields='*',
                pageToken=page_token).execute()
        except googleapiclient.errors.HttpError as e:
            print(f"Error: {e}")
            exit(1)
        for item in response.get('files', []):
            results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return results

def get_item_id(service, name_string, type='folder'):
    """Search for "folder_string" among Drive folders and folder IDs."""
    name_escaped = name_string.replace("'", "\\'")
    name_escaped = name_string
    q = f"name = '{name_escaped}'"
    if type == 'folder':
        q = f"name = '{name_escaped}' and mimeType = 'application/vnd.google-apps.folder'"
    results = get_drive_search_results(service, q)
    if len(results) > 1:
        print(f"{len(results)} results found. Please specify which item to handle:")
        for item in results:
            parents = []
            for p in item.get('parents', []):
                parents.append(service.files().get(fileId=p).execute())
            print(f"{item['name']}: {item['id']} in {[n['name'] for n in parents]} modified on {item['modifiedTime']}")
        item_id = input("\nID: ")
    if len(results) < 1:
        item_id = None
    else:
        item_id = results[0]['id']
    return item_id

def get_item_name(service, id_string):
    item = service.files().get(fileId=id_string).execute()
    return item['name']

def get_children(service, folder_id):
    query = f"'{folder_id}' in parents"
    children = get_drive_search_results(service, query)
    return children

def list_files(service, folder_name, folder_id, parents=list()):
    children = get_children(service, folder_id)
    for child in children:
        item = service.files().get(fileId=child['id']).execute()
        print('/'.join([*parents, item['name']]))
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            parents.append(item['name'])
            list_files(service, item['name'], item['id'], parents)


def run_change_owner(service, folder_string, new_owner, show_already_owned=True):
    print(f"Changing owner of \"{folder_string}\" to \"{new_owner}\"...")
    exit()
    minimum_prefix = folder_string.split('/')
    print(f"Prefix: {minimum_prefix}")
    service = get_drive_service()
    permission_id = get_permission_id_for_email(service, new_owner)
    print(f'User \"{new_owner}\" is permission ID \"{permission_id}\".')
    process_all_files(service, grant_ownership, {'permission_id': permission_id, 'show_already_owned': show_already_owned }, minimum_prefix)
    #print(files)

def run_list_files(service, folder_string):
    folder_id = get_item_id(service, folder_string)
    if not folder_id:
        print(f"Error: Folder \"{folder_string}\" not found.")
        exit(1)
    print(f"Listing all files recursively for \"{folder_string}\"...")
    parents = [folder_string]
    list_files(service, folder_string, folder_id, parents)
    exit()

def run_move_folder(service, folder_string, destination):
    print(f"Moving \"{folder_string}\" recursively to \"{destination}\" ...")
    exit()

def main():
    # Define arguments and options.
    parser = argparse.ArgumentParser(
        description="Handle actions in Drive recursively.",
        epilog="An OAuth2 link will be produced, which will need to be followed \
            by the relevant account owner. After the account owner allows the \
            app, the resulting authentication code will need to be entered.",
    )
    parser.add_argument(
        "folder",
        help="The Drive folder on which the action will be performed.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-l", "--list",
        action="store_true",
        help="list the folder's files recursively",
    )
    group.add_argument(
        "-o", "--chown",
        dest="g_account",
        metavar="user_name@sil.org",
        help="change the folder's owner to given account",
    )
    group.add_argument(
        "-m", "--move",
        dest="DEST",
        help="move the folder to given Shared drive",
    )
    parser.add_argument(
        "-d", "--dev",
        action="store_true",
        help="run in devmode"
    )
    args = parser.parse_args()

    # Retrieve appropriate credentials and drive_service.
    if args.dev:
        # Use saved credentials in devmode.
        credentials = get_dev_creds(CLIENT_SECRETS, OAUTH2_SCOPE)
    else:
        # Always get new credentials in production mode.
        credentials = get_creds(CLIENT_SECRETS, OAUTH2_SCOPE)
    drive_service = get_drive_service(credentials)

    # Parse remaining arguments and options.
    if args.list:
        run_list_files(drive_service, args.folder)
    elif args.DEST:
        run_move_folder(drive_service, args.folder, args.DEST)
    elif args.g_account:
        run_change_owner(drive_service, args.folder, args.g_account)

if __name__ == '__main__':
    main()
