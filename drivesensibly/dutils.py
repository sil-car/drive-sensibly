import logging
import sys

from dlist import list_parents_recursively


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def get_details_text(details, item, user):
    details_text = ''
    if details and not item.get('driveId', None):
        owner_email = item.get('owners')[0].get('emailAddress')
        if owner_email != user:
            details_text = f"\t({owner_email})"
    return details_text

def item_is_folder(item):
    if item.get('mimeType', None) == 'application/vnd.google-apps.folder':
        return True
    return False

def item_is_shortcut(item):
    if item.get('mimeType', None) == 'application/vnd.google-apps.shortcut':
        return True
    return False

# def item_exists(service, item_name, parent):
#     exists = False
#     children = get_children(service, parent['id'])
#     for child in children:
#         if child.get('name') == item_name:
#             exists = True
#             break
#     return exists

def get_parents_string(service, folder):
    parents = list_parents_recursively(service, folder, [])
    tree = [p['name'] for p in parents]
    tree.reverse()
    tree_string = ' > '.join(tree)
    return tree_string

def choose_item(service, results):
    if len(results) > 1:
        # eprint(f"{len(results)} results found. Please specify which item to handle:")
        logging.info(f"{len(results)} results found. Please specify which item to handle:")
        for i, obj in enumerate(results):
            parents_string = get_parents_string(service, obj)
            item_path = ' > '.join([parents_string, obj.get('name')])
            # eprint(f"   {i+1}. {item_path}")
            logging.info(f"   {i+1}. {item_path} ({obj.get('id')})")
        eprint(f"\nEnter number:")
        # logging.info(f"\nEnter number:")
        obj_num = int(input().replace('.', '').strip())
        eprint()
        # logging.info('\n')
        item = results[obj_num-1]
    elif len(results) < 1:
        item = None
    else:
        item = results[0]
    return item

def get_drive_item(service, item_id, page_token=None):
    item = None
    fields = '\
        id, name, mimeType, modifiedTime, ownedByMe, \
        sharedWithMeTime, owners, parents, permissions, capabilities \
    '
    try:
        item = service.files().get(
            fileId=item_id,
            supportsAllDrives=True,
            fields=fields,
        ).execute()
    except Exception as e:
        print(f"Error: {e}")
    return item

def get_shared_drive_list(service, name, page_token=None):
    """Get results of search query on specified account."""
    all_results = []
    while True:
        try:
            response = service.drives().list(pageToken=page_token).execute()
        except Exception as e:
            # print(f"Error: {e}")
            logging.error(e)
            exit(1)
        for item in response.get('drives', []):
            all_results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return all_results

def get_shared_drive(service, name_string=''):
    """Search for "folder_string" among Drive folders and folder IDs."""
    all_results = get_shared_drive_list(service, name_string)
    results = []
    for r in all_results:
        if r['name'] == name_string:
            results.append(r)
    item = choose_item(service, results)
    return item

def get_user_drive_search_results(service, query, page_token=None):
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
                # Limited to 'user' to speed up search.
                corpora='user',
                spaces='drive',
                supportsAllDrives=True,
                fields=fields,
                pageToken=page_token
            ).execute()
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
        for item in response.get('files', []):
            results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return results

def get_shared_drive_search_results(service, shared_drive_id, query, page_token=None):
    """Get results of search query on specified account."""
    # Get all useful fields at one time to minimize network traffic.
    fields = '\
        nextPageToken, files(id, name, driveId, mimeType, modifiedTime, ownedByMe, \
        sharedWithMeTime, owners, parents, permissions, capabilities)\
    '
    results = []
    while True:
        try:
            response = service.files().list(
                q=query,
                driveId=shared_drive_id,
                # Limited to 'drive' to speed up search.
                corpora='drive',
                spaces='drive',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields=fields,
                pageToken=page_token
            ).execute()
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
        for item in response.get('files', []):
            results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return results

def get_all_drive_search_results(service, query, page_token=None):
    """Get results of search query on specified account."""
    # Get all useful fields at one time to minimize network traffic.
    fields = '\
        nextPageToken, files(id, name, driveId, mimeType, modifiedTime, ownedByMe, \
        sharedWithMeTime, owners, parents, permissions, capabilities)\
    '
    results = []
    while True:
        try:
            response = service.files().list(
                q=query,
                corpora='allDrives',
                spaces='drive',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields=fields,
                pageToken=page_token,
            ).execute()
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
        for item in response.get('files', []):
            results.append(item)
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return results

def get_children(service, folder_id, shared_drive=None):
    query = f"'{folder_id}' in parents"
    if not shared_drive:
        children = get_user_drive_search_results(service, query)
    else:
        children = get_shared_drive_search_results(service, shared_drive.get('id'), query)
    return children

def find_drive_item(service, name_string='', type='folder', shared_drive=None, all_drives=False):
    """Search for "folder_string" among Drive folders and folder IDs."""
    name_escaped = name_string.replace("'", "\\'")
    if type == 'folder':
        q = f"name = '{name_escaped}' and not trashed and \
            mimeType = 'application/vnd.google-apps.folder'"
        if shared_drive:
            results = get_shared_drive_search_results(service, shared_drive.get('id'), q)
        elif all_drives:
            results = get_all_drive_search_results(service, q)
        else:
            results = get_user_drive_search_results(service, q)
    else:
        q = f"name = '{name_escaped}' and not trashed"
        results = get_user_drive_search_results(service, q)

    # if type == 'folder' and shared_drive:
    #     results = get_shared_drive_search_results(service, shared_drive.get('id'), q)
    # elif type == 'folder' and all_drives:
    #     q = f"name = '{name_escaped}' and not trashed and \
    #         mimeType = 'application/vnd.google-apps.folder'"
    #     results = get_all_drive_search_results(service, q)
    # elif type == 'folder':
    #     q = f"name = '{name_escaped}' and not trashed and \
    #         mimeType = 'application/vnd.google-apps.folder'"
    #     results = get_user_drive_search_results(service, q)
    # else:
    #     results = get_user_drive_search_results(service, q)

    item = choose_item(service, results)
    return item
