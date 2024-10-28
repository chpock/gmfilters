#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gmailsvc
from labels import GmailLabels
from filters import GmailFilters

if __name__ == "__main__":
    print("start...")
    service = gmailsvc.get()
    labels = GmailLabels(service)
    #for l in labels:
    #    print(l)
    filters = GmailFilters(service, labels)
    #print(filters.asYAML())
    print(filters.asYAML(custom=True))
    #for f in filters:
    #    print(f)
    #print("end...")
