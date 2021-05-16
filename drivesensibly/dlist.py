import logging

import dutils


def list_parents_recursively(service, item, parents=None):
    if parents is None:
        parents = []
    parents1_ids = item.get('parents', [])
    if len(parents1_ids) > 0:
        parents1 = []
        for p_id in parents1_ids:
            try:
                p = service.files().get(
                    fileId=p_id,
                    supportsAllDrives=True,
                    fields='id, name, mimeType, parents',
                ).execute()
            except Exception as e:
                logging.error(e)
                exit(1)
            parents1.append(p)
        # [-- Assuming 1st list item for now.
        # parents1.sort() # can't sort list of dictionaries
        parent = parents1[0]
        # --]
        parents.append(parent)
        list_parents_recursively(service, parent, parents)
    return parents

def list_files_recursively(user, service, folder, parents=list(), counts=dict(), details=False):
    pars = [p['name'] for p in parents]
    details_text = dutils.get_details_text(details, folder, user)
    # print(f"{' > '.join([*pars])}{details_text}")
    logging.info(f"{' > '.join([*pars])}{details_text}")

    # Get folder children.
    if folder.get('driveId'):
        shared_drive = dutils.get_drive_item(service, folder.get('driveId'))
        children = dutils.get_children(service, folder.get('id'), shared_drive=shared_drive)
    else:
        children = dutils.get_children(service, folder.get('id'))

    for child in children:
        child_name = child.get('name')
        counts['total_ct'] += 1
        if dutils.item_is_folder(child):
            new_parents = [*parents, child]
            counts['folder_ct'] += 1
            list_files_recursively(user, service, child, new_parents, counts, details=details)
        else:
            pars = [p['name'] for p in parents]
            details_text = dutils.get_details_text(details, child, user)
            # print(f"{' > '.join([*pars, child_name])}{details_text}")
            logging.info(f"{' > '.join([*pars, child_name])}{details_text}")
    return counts

def run_list_files(user, service, folder, details=False):
    # Process folder.
    folder_id = folder.get('id', None)
    # dutils.eprint(f"Listing all files recursively for \"{folder.get('name')}\"...")
    parents = [folder]
    counts = {'total_ct': 1, 'folder_ct': 1}
    counts = list_files_recursively(user, service, folder, parents, counts, details=details)
    # Print summary.
    folder_ct = counts['folder_ct']
    file_ct = counts['total_ct'] - folder_ct
    # Ensure proper plurals.
    d = '' if folder_ct == 1 else 's'
    f = '' if file_ct == 1 else 's'
    dutils.eprint(f"\nTotal: {folder_ct} folder{d} and {file_ct} file{f}.")
    # logging.warning(f"\nTotal: {folder_ct} folder{d} and {file_ct} file{f}.")
