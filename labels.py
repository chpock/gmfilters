#!/usr/bin/env python
# -*- coding: utf-8 -*-

SYSTEM_LABELS = (
    "CHAT", "SENT", "DRAFT",
    "INBOX", "IMPORTANT", "TRASH", "SPAM",
    "STARRED", "UNREAD",
    "CATEGORY_FORUMS", "CATEGORY_UPDATES", "CATEGORY_PERSONAL", "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"
)

def create_fake_label(name):
    return {
        "id": "FakeLabel_{}".format(name.replace(" ", "-")),
        "name": name,
        "messageListVisibility": "show",
        "labelListVisibility": "labelShowIfUnread",
        "type": "user"
    }

class GmailLabels:

    def __init__(self, gmailsvc, dry_run=False):
        self.gmailsvc = gmailsvc
        self.dry_run = dry_run
        self.reload()

    def __iter__(self):
        return iter(self.labels)

    def reload(self):
        self.labels = (self.gmailsvc.users()
            .labels()
            .list(userId="me")
            .execute()["labels"])

    def __getitem__(self, name):
        for label in self.labels:
            if label["id"] == name or label["name"] == name:
                return label
        raise KeyError(name)


