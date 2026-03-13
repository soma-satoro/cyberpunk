"""Django admin for Elflines Online."""

from django.contrib import admin
from .models import ElflineSheet, Elfline, ElflineMembership


@admin.register(ElflineSheet)
class ElflineSheetAdmin(admin.ModelAdmin):
    list_display = ("elfname", "character", "rank", "gp", "elfline", "is_complete")
    list_filter = ("rank", "revive_sickness", "is_complete")
    search_fields = ("elfname", "character__db_key")


@admin.register(Elfline)
class ElflineAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "leader")
    search_fields = ("name", "display_name")


@admin.register(ElflineMembership)
class ElflineMembershipAdmin(admin.ModelAdmin):
    list_display = ("character", "elfline", "role", "joined_at")
    list_filter = ("elfline",)
