#!/usr/bin/env python3

import argparse
import logging
import pickle

from pathlib import Path

import googleapiclient.errors

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

import dchown
import dlist
import dlog
import dmove
import dutils

OAUTH2_SCOPE = ['https://www.googleapis.com/auth/drive']
CLIENT_SECRETS = Path(__file__).parents[1] / 'client_secrets.json'


def get_dev_creds(client_secrets, scopes):
    """Used saved authentication token (only in devmode)."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token = Path(__file__).parents[1] / 'token.pickle'
    if token.is_file():
        with open(token, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(e)
        else:
            flow = Flow.from_client_secrets_file(
                client_secrets,
                scopes,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob',
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f'\nUse this link for authorization: {auth_url}')
            code = input('\nAuth. code: ').strip()
            try:
                flow.fetch_token(code=code)
            except Exception as e:
                logging.error(e)
                exit(1)
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
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        # print(f"Error: {e}")
        logging.error(e)
        exit(1)
    creds = flow.credentials
    return creds

def get_drive_service(credentials):
    drive_service = build('drive', 'v3', credentials=credentials)
    try:
        about = drive_service.about().get(fields='*').execute()
    except Exception as e:
        # print(f"Error: {e}.")
        logging.error(e)
        exit(1)
    user = about['user']
    authenticated_user = about['user']['emailAddress']
    return drive_service, authenticated_user

def return_not_found(user, folder_string):
    print(f"Error: Folder \"{folder_string}\" not found in {user}'s Drive.")
    return 1

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
        nargs='?',
        help="The Drive folder on which the action will be performed.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-d", "--dest",
        dest="DEST",
        help="move the folder to given Shared drive",
    )
    parser.add_argument(
        "-i", "--infile",
        action="store_true",
        #help="move files listed in given input file; use with -d",
        help=argparse.SUPPRESS,
    )
    group.add_argument(
        "-l", "--list",
        action="store_true",
        help="list the folder's files recursively",
    )
    group.add_argument(
        "-L", "--list-details",
        action="store_true",
        help="list the folder's file names and other details"
    )
    group.add_argument(
        "-o", "--chown",
        dest="g_account",
        metavar="user_name@sil.org",
        help="change the folder's owner to given account",
    )
    parser.add_argument(
        "-t", "--test",
        action="store_true",
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help=argparse.SUPPRESS
    )
    args = parser.parse_args()

    # Setup logging.
    loglevel = 'DEBUG' if args.verbose else 'INFO'
    dlog.setup_logging(loglevel)

    # Retrieve appropriate credentials and drive_service.
    if args.test:
        # Use saved credentials in devmode.
        credentials = get_dev_creds(CLIENT_SECRETS, OAUTH2_SCOPE)
    else:
        # Always get new credentials in production mode.
        credentials = get_creds(CLIENT_SECRETS, OAUTH2_SCOPE)
    drive_service, auth_user = get_drive_service(credentials)

    # Parse remaining arguments and options.
    list_files = args.list
    list_details = args.list_details
    folder_string = args.folder
    filelist = args.infile
    new_owner = args.g_account
    destination = args.DEST
    folder = None
    default_args = [auth_user, drive_service, folder]
    actions = {
        1: {'cmd': dlist.run_list_files, 'args': [*default_args]},
        2: {'cmd': dlist.run_list_files, 'args': [*default_args, True]},
        3: {'cmd': dchown.run_change_owner, 'args': [*default_args, new_owner]},
        4: {'cmd': dmove.run_move_folder, 'args': [*default_args, destination]},
        5: {'cmd': dmove.run_move_filelist, 'args': [*default_args, destination]},
        0: {'cmd': exit, 'args': []},
    }
    choice = -1
    if not any([list_files, list_details, new_owner, destination, filelist]):
        # Enter interactive mode.
        print(f"What do you want to do for {auth_user}?")
        options = [
            "   1. List folder contents recursively.",
            "   2. List folder content details recursively.",
            "   3. Change folder ownership recursively.",
            "   4. Move folder recursively to a Shared Drive.",
            "   5. Move files to a Shared Drive from given input file list. (not implemented)",
            "   0. Quit.",
        ]
        print('\n'.join(options))
        print()
        while choice not in actions.keys():
            choice = int(input("Choice: ").strip().replace('.', ''))

        # Get additional input, if needed.
        if choice == 1:
            list_files = True

        elif choice == 2:
            list_details == True

        elif choice == 3:
            while not new_owner:
                new_owner = input("Enter account name for new owner (user_name@sil.org): ")
                # TODO: Test that new_owner is valid?
            actions[choice]['args'][3] = new_owner

        # Temporary catch for unimplemented choice #5.
        elif choice == 5:
            dutils.eprint("Sorry, this choice is not yet implemented.")
            exit(1)

        elif choice in [4, 5]:
            while not destination:
                content = 'files' if choice == 5 else 'folder'
                destination = input(f"Enter Shared Drive location to move {content} to: ")
                # TODO: Test that destination is valid?
            actions[choice]['args'][3] = destination

    # Define choice based on command options and arguments.
    elif list_files:
        choice = 1
    elif list_details:
        choice = 2
    elif new_owner:
        choice = 3
    elif destination:
        choice = 4
    if filelist: # overrides choice 4
        choice = 5

    if choice == 0:
        # User chose 0, or choice never got defined.
        exit(0)

    # Ensure valid folder to handle.
    if not filelist:
        while not folder:
            if not folder_string:
                folder_string = input(f"Enter folder name for {auth_user}: ").strip('"')
            # Check just the last element if full path is given.
            folder_string = folder_string.split('>')[-1].strip()
            # Search for folder.
            if list_files or list_details:
                # Search user drive and shared drives.
                folder = dutils.find_drive_item(drive_service, name_string=folder_string, all_drives=True)
            else:
                # Only search user drive.
                folder = dutils.find_drive_item(drive_service, name_string=folder_string)
            if not folder:
                return_not_found(auth_user, folder_string)
                folder_string = None

        # Set folder item.
        actions[choice]['args'][2] = folder

    else:
        # Input file name is validated later.
        input_file = folder_string
        actions[choice]['args'][2] = input_file

    # Run script.
    item_id = None
    item_name = input_file
    if type(actions[choice]['args'][2]) is dict:
        item_id = actions[choice]['args'][2].get('id')
        item_name = actions[choice]['args'][2].get('name')
    logging.info(f"{actions[choice]['cmd'].__name__}, account: {auth_user}, item: \"{item_name}\" ({item_id})")
    actions[choice]['cmd'](*actions[choice]['args'])



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # dutils.eprint("\nInterrupted with Ctrl+C")
        logging.warning("Interrupted with Ctrl+C")
        exit(1)
