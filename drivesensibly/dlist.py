import dutils


def list_parents_recursively(service, item, parents):
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
                print(f"Error: {e}")
                exit(1)
            parents1.append(p)
        # [-- Assuming 1st list item for now.
        # parents1.sort() # can't sort list of dictionaries
        parent = parents1[0]
        # --]
        parents.append(parent)
        list_parents_recursively(service, parent, parents)
    return parents

def list_files_recursively(service, folder, parents=list(), counts=dict()):
    pars = [p['name'] for p in parents]
    print(f"{' > '.join([*pars])}")

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
            list_files_recursively(service, child, new_parents, counts)
        else:
            pars = [p['name'] for p in parents]
            print(f"{' > '.join([*pars, child_name])}")
    return counts

def run_list_files(user, service, folder):
    # Process folder.
    folder_id = folder.get('id', None)
    dutils.eprint(f"Listing all files recursively for \"{folder.get('name')}\"...")
    parents = [folder]
    counts = {'total_ct': 1, 'folder_ct': 1}
    counts = list_files_recursively(service, folder, parents, counts)
    # Print summary.
    folder_ct = counts['folder_ct']
    file_ct = counts['total_ct'] - folder_ct
    # Ensure proper plurals.
    d = '' if folder_ct == 1 else 's'
    f = '' if file_ct == 1 else 's'
    dutils.eprint(f"\nTotal: {folder_ct} folder{d} and {file_ct} file{f}.")
