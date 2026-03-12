"""Admin for Investigation System."""

from django.contrib import admin
from .models import Mystery, MysteryClue, CharacterFocus, ClueAttempt, ClueLocation


class ClueLocationInline(admin.TabularInline):
    model = ClueLocation
    extra = 0


class MysteryClueInline(admin.TabularInline):
    model = MysteryClue
    extra = 1


@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = ("name", "mission", "current_complexity", "max_complexity", "is_solved", "created_at")
    list_filter = ("is_solved",)
    inlines = [MysteryClueInline]


@admin.register(MysteryClue)
class MysteryClueAdmin(admin.ModelAdmin):
    list_display = ("mystery", "clue_type", "dv", "obfuscation", "damage_dice")
    list_filter = ("clue_type", "mystery")
    inlines = [ClueLocationInline]


@admin.register(ClueLocation)
class ClueLocationAdmin(admin.ModelAdmin):
    list_display = ("clue", "location_object")


@admin.register(CharacterFocus)
class CharacterFocusAdmin(admin.ModelAdmin):
    list_display = ("character_object", "character_sheet", "current_focus")


@admin.register(ClueAttempt)
class ClueAttemptAdmin(admin.ModelAdmin):
    list_display = ("character", "clue", "attempted_date", "success", "damage_dealt", "focus_lost")
