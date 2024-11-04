#!/usr/bin/env python
# -*- coding: utf-8 -*-

import click

from filters import GmailFilters

pass_filters = click.make_pass_decorator(GmailFilters)

@click.group()
@click.option("-n", "--dry-run", "dry_run",
    is_flag=True,
    show_default=True,
    default=False,
    help="do not make any changes in Gmail")
@click.pass_context
def cli(ctx, dry_run):
    ctx.obj = GmailFilters(dry_run=dry_run)

@cli.command()
@pass_filters
def download(filters):
    print("# Custom filters:")
    print("")
    filters.dumpYAML(custom=True)
    print("")
    print("")
    print("# Known filters:")
    print("")
    filters.dumpYAML(custom=False)

@cli.command()
@click.option("-f", "--filters", "stream",
    type=click.File(mode="r", encoding="utf-8"),
    default="filters.yaml",
    help="the YAML file with filters to apply")
@pass_filters
def apply(filters, stream):
    apply_filters = GmailFilters(stream=stream, labels=filters.get_labels_obj())
    filters.gmail_cleanup()
    filters.expand(apply_filters)
    filters.gmail_apply()

if __name__ == "__main__":
    cli()