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
            try:
                response = service.files().delete(
                    fileId=item.get('id'),
                ).execute()
            except Exception as e:
                print(f"Error: {e}")
            if not response:
                result = True
        elif type == 'trash':
            # Move file to the trash.
            body = {"trashed": True}
            try:
                response = service.files().update(
                    fileId=item.get('id'),
                    body=body,
                ).execute()
            except Exception as e:
                print(f"Error: {e}")
            if response.get('id'):
                result = True
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    return result

def create_folder_in_shared_drive(service, item, metadata):
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

def move_item_to_shared_drive(service, item, new_parents):
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

def move_items_recursively(service, item, destination, dest_drive):
    if not dutils.item_is_folder(item):
        # Move file.
        new_parent = destination.get('id')
        new_item_id = move_item_to_shared_drive(service, item, new_parent)
        if new_item_id:
            new_item = dutils.get_drive_item(service, new_item_id.get('id'))
        # Can't just use the returned item from "move" b/c it's lacking parent info.
        show_result(service, new_item, item)
    else:
        # Move folder and children.
        #   Check to see if folder exists in destination.
        #       List destination's children by name.
        dest_children = dutils.get_children(service, destination.get('id'), shared_drive=dest_drive)
        new_parent = None
        for dest_child in dest_children:
            if dest_child.get('name') == item.get('name'):
                new_parent = dest_child
                break
        if not new_parent:
            # Set the new folder's metadata.
            metadata = {
                'name': item.get('name', 'unnamed'),
                'parents': [destination.get('id')],
                'mimeType': 'application/vnd.google-apps.folder',
            }
            # Re-create the folder under the destination.
            new_id = create_folder_in_shared_drive(service, item, metadata)
            if new_id:
                new_parent = dutils.get_drive_item(service, new_id.get('id'))
            show_result(service, new_parent, item)

        # Move children to new folder.
        children = dutils.get_children(service, item['id'])
        for child in children:
            move_items_recursively(service, child, new_parent, dest_drive)
        # Remove empty folder.
        remove_drive_item(service, item)

def run_move_folder(user, service, folder, destination_string):
    # Ensure valid destination drive and folder.
    path_parts = destination_string.split('>')
    dest_drive_string = destination_string.split('>')[0].strip()
    dest_drive = dutils.get_shared_drive(service, name_string=dest_drive_string)
    parent_folder_string = destination_string.split('>')[-1].strip()

    ready = False
    error = f"Error: Shared Drive \"{dest_drive_string}\" not found."
    if dest_drive:
        error = f"Error: Shared Drive \"{dest_drive['name']}\" does not contain a folder called \"{parent_folder_string}\"."
        if len(path_parts) == 1:
            # Shared Drive root given with no subfolder.
            parent_folder = dutils.get_drive_item(service, dest_drive.get('id'))
        else:
            parent_folder = dutils.find_drive_item(service, name_string=parent_folder_string, shared_drive=dest_drive)
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

    print(f"Moving \"{folder['name']}\" recursively to \"{parent_folder.get('name')}\" ({parent_folder.get('id')})...")
    move_items_recursively(service, folder, parent_folder, dest_drive)
