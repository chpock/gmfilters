#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googleapiclient.discovery

SCOPES = [
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.labels",
]

CLIENT_SECRET = "client_secret.json"

APPLICATION_NAME = "gmf"

CREDENTIALS_FILE = "credentials.pickle"
CREDENTIALS_STORE = os.path.join(
    os.path.expanduser("~"),
    ".gmf",
    CREDENTIALS_FILE
)

def get_credentials():

    if not os.path.exists(os.path.dirname(os.path.abspath(CREDENTIALS_STORE))):
        os.makedirs(os.path.dirname(os.path.abspath(CREDENTIALS_STORE)))

    creds = None

    if os.path.exists(CREDENTIALS_STORE):
        with open(CREDENTIALS_STORE, "rb") as fp:
            creds = pickle.load(fp)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CREDENTIALS_STORE, 'wb') as fp:
            pickle.dump(creds, fp)

    return creds


def get(credentials=None):
    if not credentials:
        credentials = get_credentials()
    service = googleapiclient.discovery.build("gmail", "v1", credentials=credentials)
    return service
