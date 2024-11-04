#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import re
import sys
from collections.abc import Iterable

from ruamel.yaml import YAML

from labels import SYSTEM_LABELS
from labels import GmailLabels
import gmailsvc

class YamlProcessingError(Exception):
    pass

class YamlProcessingFieldsError(YamlProcessingError):

    def __init__(self, fields, block):
        if self.is_many(fields):
            frm = self.format_many
        else:
            frm = self.format_single
        message = frm.format(fields=self.many2one(fields), block=block)
        super().__init__(message)

    @staticmethod
    def is_many(fields):
        return isinstance(fields, Iterable) and len(fields) > 1

    @staticmethod
    def many2one(fields):
        if not isinstance(fields, Iterable):
            return fields
        elif len(fields) == 1:
            return list(fields)[0]
        else:
            return '", "'.join(fields)

class YamlMissingFieldsError(YamlProcessingFieldsError):
    def __init__(self, fields, block):
        self.format_many = 'Missing required fields "{fields}" in block "{block}".'
        self.format_single = 'Missing required field "{fields}" in block "{block}".'
        super().__init__(fields, block)

class YamlUnknownFieldsError(YamlProcessingFieldsError):
    def __init__(self, fields, block):
        self.format_many = 'Unknown fields "{fields}" in block "{block}".'
        self.format_single = 'Unknown field "{fields}" in block "{block}".'
        super().__init__(fields, block)

class YamlUnknownFilterFieldsError(YamlProcessingFieldsError):
    def __init__(self, fields, block):
        self.format_many = 'Unknown fields "{fields}" in filter block "{block}".'
        self.format_single = 'Unknown field "{fields}" in filter block "{block}".'
        super().__init__(fields, block)

class YamlUnknownActionFieldsError(YamlProcessingFieldsError):
    def __init__(self, fields, block):
        self.format_many = 'Unknown fields "{fields}" in action block "{block}".'
        self.format_single = 'Unknown field "{fields}" in action block "{block}".'
        super().__init__(fields, block)

class YamlOnlyOneExpectedError(YamlProcessingError):
    def __init__(self, field, block):
        message = f'Field "{field} is expected to be the only one, but additional fields were found in block "{block}"'
        super().__init__(message)

class YamlOnlyTrueExpectedError(YamlProcessingError):
    def __init__(self, field, value, block):
        message = f'Field "{field}" is expected with value "true", but value "{value}" was found in block "{block}"'
        super().__init__(message)

class GmailFilter:

    def __init__(self, data, labels):

        if "criteria" not in data:
            data = self.normalize(data)

        self.data = data
        self.labels = labels

    def __str__(self):
        return str(self.data)

    def id(self):
        return self.data["id"]

    def dump_for_yaml(self):

        # Check criteria for well-known patterns
        if criteria_list := self.get_criteria_list():
            dump = { "filter": {"list": criteria_list} }
        else:
            dump = { "filter": self.data["criteria"] }

        # Check actions for well-known patterns
        action = {}
        if move_to := self.get_move_to():
            action["move_to"] = move_to
        elif copy_to := self.get_copy_to():
            action["copy_to"] = copy_to
        elif self.is_delete():
            action["delete"] = True
        else:
            labels = self.get_labels(skip_important=True)
            if labels:
                action["label"] = labels
            labels = self.get_unlabels()
            if labels:
                action["unlabel"] = labels
        if self.is_important():
            action["important"] = True

        # Add action to the dump
        if action:
            dump["action"] = action

        return dump

    def is_custom(self):
        return (
            "size" not in self.data["criteria"] or
            "sizeComparison" not in self.data["criteria"] or
            self.data["criteria"]["size"] != 1 or
            self.data["criteria"]["sizeComparison"] != "larger"
        )

    def get_move_to(self):
        lb, unlb = self.get_all_labels(use_id=True, skip_spam=True, skip_important=True)
        if len(lb) != 1 or len(unlb) != 1 or unlb[0] != "INBOX":
            return ""
        return self.labels[lb[0]]["name"]

    def get_copy_to(self):
        lb, unlb = self.get_all_labels(use_id=True, skip_spam=True, skip_important=True)
        if len(lb) != 1 or len(unlb) != 0:
            return ""
        return self.labels[lb[0]]["name"]

    def get_criteria_list(self):
        # Make sure we have only 1 criteria and it is "query"
        if len(self.data["criteria"]) != 1 or "query" not in self.data["criteria"]:
            return ""
        match = re.search(r'^list:\(?(.+?)\)?$', self.data["criteria"]['query'])
        if not match:
            return ""
        return match[1]

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

    def normalize_labels(self):
        for field in ("addLabelIds", "removeLabelIds"):
            if field in self.data["action"]:
                for i, label in enumerate(self.data["action"][field]):
                    self.data["action"][field][i] = self.labels.id(self.data["action"][field][i])
        return self

    def to_dict(self):
        return self.data

    @staticmethod
    def normalize(data):
        # print("\nNORM FROM:", data)

        # Make sure we have both filter and action sections

        expected_fields = { "filter", "action" }
        if fields := expected_fields - set(data):
            raise YamlMissingFieldsError(fields, data)

        if fields := set(data) - expected_fields:
            raise YamlUnknownFieldsError(fields, data)

        # Normalize criteria (filter) section

        if "list" in data["filter"]:
            if len(data["filter"]) != 1:
                raise YamlOnlyOneExpectedError("list", data["filter"])
            criteria = {"query": f"list:({data["filter"]["list"]})"}
        else:
            criteria = {}
            raw_criteria = { "from", "to", "query", "subject" }
            if fields := set(data["filter"]) - raw_criteria:
                raise YamlUnknownFilterFieldsError(fields, data)
            for key in raw_criteria:
                if key in data["filter"]:
                    criteria[key] = data["filter"][key]

        criteria["size"] = 1
        criteria["sizeComparison"] = "larger"

        result = { "criteria": criteria }

        # Normalize action section

        action = { "addLabelIds": [], "removeLabelIds": [] }

        if "important" in data["action"]:
            if data["action"]["important"] != True:
                raise YamlOnlyTrueExpectedError("important", data["action"]["important"], data)
            action["addLabelIds"].append("IMPORTANT")
            del data["action"]["important"]

        normalize_actions = { "copy_to", "move_to", "delete" }
        is_normalized = False
        for one_action in normalize_actions:
            if one_action in data["action"]:

                if len(data["action"]) != 1:
                    raise YamlOnlyOneExpectedError(one_action, data["action"])

                if one_action == "copy_to" or one_action == "move_to":
                    action["addLabelIds"].append(data["action"][one_action])
                elif one_action == "delete":
                    if data["action"][one_action] != True:
                        raise YamlOnlyTrueExpectedError(one_action, data["action"][one_action], data)
                    action["addLabelIds"].append("TRASH")
                else:
                    raise Exception(f"no normalization rule for action: {one_action}")

                action["removeLabelIds"].append("SPAM")

                if one_action == "move_to" or one_action == "delete":
                    action["removeLabelIds"].append("INBOX")

                is_normalized = True

        if not is_normalized:
            if "label" in data["action"]:
                action["addLabelIds"].extend(data["action"]["label"])
            if "unlabel" in data["action"]:
                action["removeLabelIds"].extend(data["action"]["unlabel"])

        if not len(action["addLabelIds"]):
            del action["addLabelIds"]
        if not len(action["removeLabelIds"]):
            del action["removeLabelIds"]
        if len(action):
            result["action"] = action

        #print("NORM TO  :", result)
        return result

# CHAT SENT DRAFT
# INBOX IMPORTANT TRASH SPAM
# STARRED UNREAD
# CATEGORY_FORUMS CATEGORY_UPDATES CATEGORY_PERSONAL CATEGORY_PROMOTIONS CATEGORY_SOCIAL

class GmailFilters:

    def __init__(self, service=None, stream=None, labels=None, dry_run=False):

        if service == None and stream == None:
            service = gmailsvc.get()

        if labels == None:
            labels = GmailLabels(service)

        self.service = service
        self.dry_run = dry_run
        self.labels = labels

        self.reload(stream)

    def __iter__(self):
        return iter((f for f in self.filters if not f.is_custom()))

    def reload(self, stream):
        if stream != None:
            yaml = YAML(typ='safe')
            data = yaml.load(stream)
            self.filters = list(map(lambda d: GmailFilter(d, labels=self.labels), data))
        else:
            self.filters = list(map(lambda d: GmailFilter(d, labels=self.labels), (self.service.users()
                .settings()
                .filters()
                .list(userId="me")
                .execute()
                .get("filter", []))))

    def get_labels_obj(self):
        return self.labels

    def get_custom_filters(self):
        return (f for f in self.filters if f.is_custom())

    def dumpYAML(self, custom=False):
        data = [f.dump_for_yaml() for f in self.filters if (custom and f.is_custom()) or (not custom and not f.is_custom())]
        if not data:
            return ""
        # Use pure=True to be able to specify indentation
        yaml = YAML(typ='safe', pure=True)
        yaml.width = 1000
        yaml.default_flow_style = False
        yaml.sort_base_mapping_type_on_output = False
        yaml.indent(mapping=2, sequence=4, offset=2)
        yaml.dump(data, sys.stdout)

    def expand(self, filters):
        for f in filters:
            self.filters.append(f.normalize_labels())

    def gmail_cleanup(self):
        new_filters = []
        for f in self.filters:

            if f.is_custom():
                new_filters.append(f)
                continue

            if self.dry_run:
                print("Remove from Gmail filters:", f)
            else:
                pass
                self.service.users().settings().filters().delete(userId="me", id=f.id()).execute()

        self.filters = new_filters

    def gmail_apply(self):
        for f in self.filters:

            if f.is_custom():
                continue

            if self.dry_run:
                print("Create Gmail filter:", f)
            else:
                pass
                self.service.users().settings().filters().create(userId="me", body=f.to_dict()).execute()

