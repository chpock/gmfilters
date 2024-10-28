#!/usr/bin/env python
# -*- coding: utf-8 -*-
import yaml
import copy
from labels import SYSTEM_LABELS

class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)

class GmailFilter:

    def __init__(self, labels, data):
        self.data = data
        self.labels = labels

    def __str__(self):
        return str(self.data)

    def dump_for_yaml(self):
        dump = self.data["criteria"]
        actions = {}
        if move_to := self.get_move_to():
            actions["move_to"] = move_to
        elif self.is_delete():
            actions["delete"] = True
        else:
            labels = self.get_labels(skip_important=True)
            if labels:
                actions["label"] = labels
            labels = self.get_unlabels()
            if labels:
                actions["unlabel"] = labels
        if self.is_important():
            actions["important"] = True
        if actions:
            dump["actions"] = actions
        return dump

    def is_custom(self):
        return (
            "size" not in self.data["criteria"] or
            "sizeComparison" not in self.data["criteria"] or
            self.data["criteria"]["size"] != 0 or
            self.data["criteria"]["sizeComparison"] != "larger"
        )

    def get_move_to(self):
        lb, unlb = self.get_all_labels(use_id=True, skip_spam=True, skip_important=True)
        if len(lb) != 1 or len(unlb) != 1 or unlb[0] != "INBOX":
            return ""
        return self.labels[lb[0]]["name"]

    def is_important(self):
        lb = self.get_labels(use_id=True)
        return "IMPORTANT" in lb

    def is_delete(self):
        lb, unlb = self.get_all_labels(use_id=True, skip_spam=True)
        if len(lb) == 1 and lb[0] == "TRASH" and (len(unlb) == 0 or unlb[0] == "UNREAD"):
            return True
        return False

    def get_labels(self, use_id=False, skip_important=False):
        if "addLabelIds" not in self.data["action"]:
            return []
        if use_id:
            result = self.data["action"]["addLabelIds"].copy()
        else:
            result = [self.labels[l]["name"] for l in self.data["action"]["addLabelIds"]]
        if skip_important and "IMPORTANT" in result:
            result.remove("IMPORTANT")
        return result

    def get_unlabels(self, use_id=False, skip_spam=False):
        if "removeLabelIds" not in self.data["action"]:
            return []
        if use_id:
            result = self.data["action"]["removeLabelIds"].copy()
        else:
            result = [self.labels[l]["name"] for l in self.data["action"]["removeLabelIds"]]
        if skip_spam and "SPAM" in result:
            result.remove("SPAM")
        return result

    def get_all_labels(self, use_id=False, skip_spam=False, skip_important=False):
        return (self.get_labels(use_id=use_id, skip_important=skip_important), self.get_unlabels(use_id=use_id, skip_spam=skip_spam))


# CHAT SENT DRAFT
# INBOX IMPORTANT TRASH SPAM
# STARRED UNREAD
# CATEGORY_FORUMS CATEGORY_UPDATES CATEGORY_PERSONAL CATEGORY_PROMOTIONS CATEGORY_SOCIAL

class GmailFilters:

    def __init__(self, gmailsvc, labels, dry_run=False):
        self.gmailsvc = gmailsvc
        self.dry_run = dry_run
        self.labels = labels
        self.reload()

    def __iter__(self):
        return iter((f for f in self.filters if not f.is_custom()))

    def reload(self):
        self.filters = list(map(lambda d: GmailFilter(self.labels, d), (self.gmailsvc.users()
            .settings()
            .filters()
            .list(userId="me")
            .execute()
            .get("filter", []))))

    def get_custom_filters(self):
        return (f for f in self.filters if f.is_custom())

    def asYAML(self, custom=False):
        data = [f.dump_for_yaml() for f in self.filters if (custom and f.is_custom()) or (not custom and not f.is_custom())]
        return yaml.dump(data, sort_keys=False, width=999, allow_unicode=True, Dumper=MyDumper)

