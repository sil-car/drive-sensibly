import dutils


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

    if dutils.item_is_shortcut(item):
        # # Shortcuts don't have "permissions" entries.
        # full_item = utils.get_drive_item(service, item.get('id'))
        # if full_item:
        #     owners = full_item.get('owners', [])
        '''
        {'id': '15FeyUKN7RF_FnG_dLcVg0az5-MNd6nPL', 'name': 'Monday Feb 22 LP.pdf', 'mimeType': 'application/vnd.google-apps.shortcut', 'parents': ['1-1mFkhE4b2h1caLcIE_wUTkcCFphxzO9'], 'modifiedTime': '2021-05-04T09:57:42.427Z', 'owners': [{'kind': 'drive#user', 'displayName': 'IT Admin CAR', 'me': True, 'permissionId': '02558864029776463543', 'emailAddress': 'it_admin_car@sil.org'}], 'ownedByMe': True}
        '''
        #body = {'owners': owners.append()}
        print(f"Can't change owner of shortcut \"{item.get('name')}\".")
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
            except Exception as e:
                print(f"Error: {e}")
                return False

def change_owner_recursively(service, item, new_owner, parents=list()):
    # Handle item.
    result = change_item_owner(service, item, new_owner)
    x = '\u2713' if result else '\u2717'
    print(f"{x} {' > '.join(parents)}")

    # Handle item's children.
    if dutils.item_is_folder(item):
        children = dutils.get_children(service, item['id'])
        for child in children:
            new_parents = [*parents, child['name']]
            change_owner_recursively(service, child, new_owner, new_parents)

def run_change_owner(user, service, folder, new_owner, show_already_owned=True):
    # Process folder.
    folder_id = folder.get('id', None)
    print(f"Changing owner of \"{folder['name']}\" to \"{new_owner}\"...")
    change_owner_recursively(service, folder, new_owner, [folder['name']])
