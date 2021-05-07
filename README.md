# DriveSensibly

Manage recursive actions in Google Drive:
- List files
- Change ownership
- Move folder to a Shared drive

This is not available as an installable package, but you can do one of the following:
- Run it yourself by:
  - cloning the repo
  - installing the pip3 requirements
  - creating your own Google Developers API project
  - adding the resulting "client_secrets.json" to the top level of the repo
  - run it with `$ python3 drivesensibly/app.py [--help]`
- Request SIL-CAR to run it on your behalf using the contact form on the repo's home page: https://github.com/sil-car/home.

### App authorization link
Following this link will allow you to authorize "DriveSensiby (SIL-CAR)" to access your Google Drive account. It's given here mostly for reference.
https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=561275927099-8qcsin52f0j8m9jcop795jbn505c7avr.apps.googleusercontent.com&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive&state=QnfAmu4HcomaKyrOpy9WENvVDDECnY&prompt=consent&access_type=offline
