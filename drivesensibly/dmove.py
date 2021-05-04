import googleapiclient.errors

import dutils

from dlist import list_parents_recursively


def show_result(service, result, item):
    if result:
        parents_string = dutils.get_parents_string(service, result)
        x = '\u2713'
        print(f"{x} {parents_string} > {result.get('name')}")
    else:
        x = '\u2717'
        print(f"{x} {item.get('name')}")

def remove_drive_item(service, item, type='delete'):
    result = False
    if dutils.item_is_folder(item):
        children = dutils.get_children(service, item.get('id'))
        if children:
            print(f"Error: Folder \"{item.get('name')}\" is not empty. Skipping removal.")
            return result
    try:
        if type == 'delete':
            # Delete file.
            response = service.files().delete(
                fileId=item.get('id'),
            ).execute()
            if not response:
                result = True
        elif type == 'trash':
            # Move file to the trash.
            body = {"trashed": True}
            response = service.files().update(
                fileId=item.get('id'),
                body=body,
            ).execute()
            if response.get('id'):
                result = True
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    return result

def get_shared_drive_list(service, name, page_token=None):
    """Get results of search query on specified account."""
    all_results = []
    while True:
        try:
            response = service.drives().list(pageToken=page_token).execute()
        except Exception as e:
            print(f"Error: {e}")
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
    item = dutils.choose_item(service, results)
    return item

def create_folder_in_shared_drive(user, service, item, metadata):
    # Re-create the folder under the destination.
    #   Returns new-item id dict.
    try:
        result = service.files().create(
            body=metadata,
            supportsAllDrives=True,
            fields='id',
        ).execute()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    return result

def move_item_to_shared_drive(user, service, item, new_parents):
    # Move the file into the destination.
    try:
        result = service.files().update(
            fileId=item['id'],
            addParents=new_parents,
            supportsAllDrives=True,
            removeParents=f"{','.join(item.get('parents'))}"
        ).execute()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    return result

def move_items_recursively(user, service, item, destination, folders_list, dest_drive):
    if not dutils.item_is_folder(item):
        # Move file.
        new_parent = destination.get('id')
        new_id = move_item_to_shared_drive(user, service, item, new_parent)
        if new_id:
            new_item = dutils.get_drive_item(service, new_id.get('id'))
        show_result(service, new_item, item)
    else:
        # Move folder and children.
        # Add item to folder_list to be removed later.
        folders_list.append(item)
        # Check to see if folder exists in destination.
        # new_parent = get_shared_drive_item(service, dest_drive.get('id'), name=item.get('name'))
        new_parent = dutils.find_drive_item(service, name_string=item.get('name'), shared_drive=dest_drive)
        if not new_parent:
            # Set the new folder's metadata.
            metadata = {
                'name': item.get('name', 'unnamed'),
                'parents': [destination.get('id')],
                'mimeType': 'application/vnd.google-apps.folder',
            }
            # Re-create the folder under the destination.
            new_id = create_folder_in_shared_drive(user, service, item, metadata)
            new_parent = None
            if new_id:
                new_parent = dutils.get_drive_item(service, new_id.get('id'))
            show_result(service, new_parent, item)

        # Move children to new folder.
        children = dutils.get_children(service, item['id'])
        for child in children:
            move_items_recursively(user, service, child, new_parent, folders_list, dest_drive)
        # Remove empty folder.
        remove_drive_item(service, item)

def run_move_folder(user, service, folder, destination_string):
    # Ensure valid destination drive and folder.
    dest_drive_string = destination_string.split('>')[0].strip()
    parent_folder_string = destination_string.split('>')[-1].strip()
    dest_drive = get_shared_drive(service, name_string=dest_drive_string)

    ready = False
    error = f"Error: Shared Drive \"{dest_drive_string}\" not found."
    if dest_drive:
        error = f"Error: Shared Drive \"{dest_drive['name']}\" does not contain a folder called \"{parent_folder_string}\"."
        # parent_folder = get_shared_drive_item(service, dest_drive['id'], name=parent_folder_string)
        parent_folder = dutils.find_drive_item(service, name_string=parent_folder_string, shared_drive=dest_drive)
        print(parent_folder)
        if parent_folder:
            # Check if parent_folder is writable by user.
            dest_caps = parent_folder.get('capabilities', None)
            error = f"Error: {user} cannot add items to {dest_drive['name']}."
            if dest_caps:
                if dest_caps.get('canAddChildren', None):
                    ready = True
    if not ready:
        print(error)
        return 1

    print(f"Moving \"{folder['name']}\" recursively to \"{parent_folder['name']}\" ...")
    folders_to_remove = [folder]
    move_items_recursively(user, service, folder, parent_folder, folders_to_remove, dest_drive)
