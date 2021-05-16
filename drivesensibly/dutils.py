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

def get_parents_string(service, item):
    parents = list_parents_recursively(service, item, [])
    tree = [p['name'] for p in parents]
    tree.reverse()
    parents_path_string = ' > '.join(tree)
    return parents_path_string

def get_item_path(service, item):
    parents_path = get_parents_string(service, item)
    item_path = f"{parents_path} > {item.get('name')}"
    return item_path

################################################################################
def get_item_from_path(service, path_names, path_items=None):
    if path_items == None:
        path_items = []
    # path is a list of strings like ["My Drive", "folder", "item"]
    item_name = path_names.pop()
    candidate_items = search_drive_item_name(service, name_string=item_name, type='any')
    candidate_paths = [[ci] for ci in candidate_items]
    for path in candidate_paths:
        new_path = add_parent_to_path(service, path)
        # Compare parent names.
        if new_path[0].get('name') == path_names[0]:
            # Keep this path.
            new_new_path = add_parent_to_path(service, path)

def expand_path_names_to_items(service, path_names, path_items=None):
    """
    Convert path given as string to list of items.
    """
    # Setup variables.
    if path_items is None:
        path_items = []
    path_items_names = [i.get('name') for i in path_items]
    logging.debug(f"path_names: {path_names}")
    logging.debug(f"path_items_names: {path_items_names}")
    # Handle base case.
    if path_items_names == path_names:
        details = [f"{i.get('name')} ({i.get('id')})" for i in path_items]
        logging.debug(f"Names: {' > '.join(path_names)}")
        logging.debug(f"Expansion: {' > '.join(details)}")
        return path_items
    else:
        # Handle recursive case: Get next path_item.
        if len(path_items) == 0:
            # Find first path_item.
            next_i_in_names = len(path_names) - 1
            logging.debug(f"next_i_in_names: {next_i_in_names}")
            next_name = path_names[next_i_in_names]
            logging.debug(f"next_name: {next_name}")
            next_potential_items = search_drive_item_name(service, name_string=next_name, type='any')
            logging.info(f"{len(next_potential_items)} matching items found for \"{next_name}\".")

            # Determine which found items have the right parent folder name.
            next_approved_items = []
            for npi in next_potential_items:
                # Get remaining names in path_items_names.
                next_parents_names = path_names[:next_i_in_names]
                logging.debug(f"next_parent_names: {next_parents_names}")

                # Get parent_path_names to same depth as path_names.
                npi_parents_items = list_parents_recursively(service, npi)[::-1]
                npi_parents_names = [n.get('name') for n in npi_parents_items[-len(next_parents_names):]]
                logging.debug(f"npi_parents_names: {npi_parents_names}")

                # Add this next_item to next_approved_items if the lists match.
                if npi_parents_names == next_parents_names:
                    logging.info(f"Keeping \"{npi.get('name')}\" ({npi.get('id')})")
                    next_approved_items.append(npi)

            if len(next_approved_items) > 1:
                nai_stats = [(i.get('name'), i.get('id')) for i in next_approved_items]
                logging.debug(f"Too many possibilities: {nai_stats}")
                return []
            elif len(next_approved_items) == 1:
                path_items.append(next_approved_items[0])
                path_items = expand_path_names_to_items(service, path_names, path_items)
                return path_items
        else:
            # Get parent of most recent path_item.
            prev_item = path_items[0]
            prev_item_parent_id = prev_item.get('parents')[0]
            next_item = get_drive_item(service, prev_item_parent_id)
            logging.debug(f"next_item.name|id: {next_item.get('name')}|{next_item.get('id')}")
            # Append to path_items, continue search.
            path_items.insert(0, next_item)
            path_items = expand_path_names_to_items(service, path_names, path_items)
            return path_items

def match_parents(service, parent_names, items):
    candidate_parents = []
    parent_name = parent_names.pop()
    for item in items:
        candidate_parent_id = item.get('parents', [])[0]
        candidate_parent_item = get_drive_item(service, candidate_parent_id)
        candidate_parent_name = candidate_parent_item.get('name')
        if candidate_parent_name == parent_name:
            candidate_parents.append()
    if len(candidate_parents) > 1:
        match_parents(service, parent_names, candidate_parents)
    else:
        return candidate_parents[0]
################################################################################
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

def get_drive_item(service, item_id):
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
        # print(f"Error: {e}")
        logging.error(e)
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

def validate_shared_drive_destination(service, dest_drive_string, dest_path_names):
    logging.debug(f"Given string: {dest_drive_string}")
    dest_drive = get_shared_drive(service, name_string=dest_drive_string)
    logging.debug(f"Search results: {dest_drive}")
    parent_folder_string = dest_path_names[-1]

    ready = False
    error = f"Error: Shared Drive \"{dest_drive_string}\" not found."
    if dest_drive:
        error = f"Error: Shared Drive \"{dest_drive.get('name')}\" does not contain a folder called \"{parent_folder_string}\"."
        if len(dest_path_names) == 1:
            # Shared Drive root given with no subfolder.
            parent_folder = get_drive_item(service, dest_drive.get('id'))
        else:
            parent_folder = find_drive_item(service, name_string=parent_folder_string, shared_drive=dest_drive)
        if parent_folder:
            # Check if parent_folder is writable by user.
            dest_caps = parent_folder.get('capabilities', None)
            error = f"Error: User cannot add items to {dest_drive.get('name')}."
            if dest_caps:
                if dest_caps.get('canAddChildren', None):
                    ready = True
    if not ready:
        logging.error(error)
        return None
    return dest_drive

def get_shared_drive(service, name_string=''):
    """Search for "folder_string" among Drive folders and folder IDs."""
    all_results = get_shared_drive_list(service, name_string)
    results = []
    for r in all_results:
        if r['name'] == name_string:
            results.append(r)
    item = choose_item(service, results)
    return item

def get_shared_drive_name_from_path_string(path_string):
    dest_drive_string = path_string.split('>')[0].strip()
    return dest_drive_string

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

def search_drive_item_name(service, name_string='', type='folder'):
    """Search for "name_string" among Drive folders and folder IDs."""
    name_escaped = name_string.replace("'", "\\'")
    if type == 'folder':
        q = f"name = '{name_escaped}' and not trashed and \
            mimeType = 'application/vnd.google-apps.folder'"
    else:
        q = f"name = '{name_escaped}' and not trashed"
    items = get_all_drive_search_results(service, q)
    return items

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
