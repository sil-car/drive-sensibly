#!/usr/bin/env python3

import argparse
import pickle

from pathlib import Path

# import googleapiclient.http
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
    print()
    flow.fetch_token(code=code)
    creds = flow.credentials
    return creds

def get_drive_service(credentials):
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

def get_drive_search_results(service, query, page_token=None):
    """Get results of search query on specified account."""
    # Get all useful fields at one time to minimize network traffic.
    fields = '\
        nextPageToken, files(id, name, mimeType, modifiedTime, ownedByMe, \
        sharedWithMeTime, owners, parents, permissions)\
    '
    results = []
    while True:
        try:
            response = service.files().list(
                q=query,
                spaces='drive',
                supportsAllDrives=True,
                fields=fields,
                pageToken=page_token
            ).execute()
        except googleapiclient.errors.HttpError as e:
            print(f"Error: {e}")
            exit(1)
        for item in response.get('files', []):
            results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return results

def get_item(service, name_string, type='folder'):
    """Search for "folder_string" among Drive folders and folder IDs."""
    name_escaped = name_string.replace("'", "\\'") # doesn't work
    name_escaped = name_string
    q = f"name = '{name_escaped}' and not trashed"
    if type == 'folder':
        q = f"name = '{name_escaped}' and \
            mimeType = 'application/vnd.google-apps.folder' and \
            not trashed"
    results = get_drive_search_results(service, q)
    if len(results) > 1:
        print(f"{len(results)} results found. Please specify which item to handle:")
        for i, item in enumerate(results):
            parents_string = get_parents_string(service, item)
            print(f"   {i+1}. {parents_string}")
        item_num = int(input("\nEnter number: ").replace('.', '').strip())
        print()
        item_id = results[item_num-1]['id']
    if len(results) < 1:
        item_id = None
    else:
        item = results[0]
    return item

def get_item_name(service, id_string):
    item = service.files().get(fileId=id_string).execute()
    return item['name']

def get_children(service, folder_id):
    query = f"'{folder_id}' in parents"
    children = get_drive_search_results(service, query)
    return children

def change_item_owner(service, item, new_owner):
    # Check current ownership.
    owners = item.get('owners', None)
    for o in owners:
        if o['emailAddress'] == new_owner:
            # Permissions are already correct.
            return True
    if not item.get('ownedByMe', None):
        # Can't transfer ownership if not current owner.
        return False

    # Transfer ownership.
    permissions = item.get('permissions', None)
    for permission in permissions:
        account = permission.get('emailAddress', None)
        if account == new_owner:
            # Set this account as owner.
            updated_permission = {'role': 'owner'}
            try:
                result = service.permissions().update(
                    fileId=item['id'],
                    permissionId=permission['id'],
                    body=updated_permission,
                    supportsAllDrives=True,
                    transferOwnership=True,
                ).execute()
                return True
            except googleapiclient.errors.HttpError as e:
                print(f"Error: {e}")
                return False

def get_parents_string(service, folder):
    parents = list_parents_recursively(service, folder)
    tree = [p['name'] for p in parents]
    tree.insert(0, folder['name'])
    tree.reverse()
    tree_string = ' > '.join(tree)
    return tree_string

def change_owner_recursively(service, item, new_owner, parents=list()):
    # Handle item.
    result = change_item_owner(service, item, new_owner)
    x = '\u2713' if result else '\u2717'
    print(f"{x} {' > '.join(parents)}")

    # Handle item's children.
    if item['mimeType'] == 'application/vnd.google-apps.folder':
        children = get_children(service, item['id'])
        for child in children:
            new_parents = [*parents, child['name']]
            change_owner_recursively(service, child, new_owner, new_parents)

def list_parents_recursively(service, folder, parents=list()):
    parents1_ids = folder.get('parents', [])
    if len(parents1_ids) > 0:
        parents1 = []
        for p_id in parents1_ids:
            p = service.files().get(
                fileId=p_id,
                #fields='id, name, mimeType, modifiedTime, ownedByMe, sharedWithMeTime, parents, permissions',
                fields='id, name, mimeType, parents',
            ).execute()
            parents1.append(p)
        # [-- Assuming 1st list item for now.
        parents1.sort() # use oldest? is it listed first?
        parent = parents1[0]
        # --]
        parents.append(parent)
        list_parents_recursively(service, parent, parents)
    return parents

def list_files_recursively(service, folder, parents=list(), tree=dict(), counts=dict()):
    children = get_children(service, folder['id'])
    for child in children:
        child_name = child['name']
        counts['total_ct'] += 1
        # [-- Working on building a tree...
        # d = parents[:]
        # here = tree.copy()
        # while d:
        #     here = here[d.pop()]
        # print(here)
        # --]
        pars = [p['name'] for p in parents]
        print(f"{' > '.join([*pars, child_name])}")
        if child['mimeType'] == 'application/vnd.google-apps.folder':
            new_parents = [*parents, child]
            counts['folder_ct'] += 1
            list_files_recursively(service, child, new_parents, tree, counts)
    return tree, counts

def run_change_owner(service, folder_string, new_owner, show_already_owned=True):
    folder_item = get_item(service, folder_string)
    folder_id = folder_item.get('id', None)
    if not folder_id:
        print(f"Error: Folder \"{folder_string}\" not found.")
        exit(1)
    print(f"Changing owner of \"{folder_string}\" to \"{new_owner}\"...")
    change_owner_recursively(service, folder_item, new_owner, [folder_string])

def run_list_files(service, folder_string):
    folder = get_item(service, folder_string)
    folder_id = folder['id']
    if not folder_id:
        print(f"Error: Folder \"{folder_string}\" not found.")
        exit(1)
    print(f"Listing all files recursively for \"{folder_string}\"...")
    parents = [folder]
    tree = {folder['name']: None}
    counts = {'total_ct': 1, 'folder_ct': 1}
    tree, counts = list_files_recursively(service, folder, parents, tree, counts)
    folder_ct = counts['folder_ct']
    file_ct = counts['total_ct'] - folder_ct
    # Ensure proper plurals.
    d = '' if folder_ct == 1 else 's'
    f = '' if file_ct == 1 else 's'
    print(f"\nTotal: {folder_ct} folder{d} and {file_ct} file{f}.")

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
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted with Ctrl+C")
        exit(1)
