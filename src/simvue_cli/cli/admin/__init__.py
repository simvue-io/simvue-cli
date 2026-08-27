"""Simvue Server Admin Commands."""

import click

from .user import simvue_user as user_cli
from .tenant import simvue_tenant as tenant_cli


@click.group("admin")
@click.pass_context
def admin(_) -> None:
    """Administrator commands, require admin access"""
    pass


admin.add_command(user_cli)
admin.add_command(tenant_cli)
