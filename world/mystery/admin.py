"""Admin for Investigation System."""

from django.contrib import admin
from .models import (
    Mystery,
    MysteryClue,
    MysteryObstacle,
    CharacterFocus,
    ClueAttempt,
    ClueLocation,
    ObstacleAttempt,
    ClueExposure,
)


class ClueLocationInline(admin.TabularInline):
    model = ClueLocation
    extra = 0


class MysteryClueInline(admin.TabularInline):
    model = MysteryClue
    extra = 1


class MysteryObstacleInline(admin.TabularInline):
    model = MysteryObstacle
    extra = 0


@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = ("name", "difficulty_level", "mission", "current_complexity", "max_complexity", "is_solved", "created_at")
    list_filter = ("is_solved", "difficulty_level")
    inlines = [MysteryClueInline, MysteryObstacleInline]


@admin.register(MysteryClue)
class MysteryClueAdmin(admin.ModelAdmin):
    list_display = (
        "mystery",
        "clue_type",
        "dv",
        "discovery_priority",
        "gating_obstacle",
        "obfuscation",
        "damage_dice",
    )
    list_filter = ("clue_type", "mystery")
    inlines = [ClueLocationInline]


@admin.register(ClueLocation)
class ClueLocationAdmin(admin.ModelAdmin):
    list_display = ("clue", "location_object", "element_key")


@admin.register(CharacterFocus)
class CharacterFocusAdmin(admin.ModelAdmin):
    list_display = ("character_object", "character_sheet", "current_focus")


@admin.register(ClueAttempt)
class ClueAttemptAdmin(admin.ModelAdmin):
    list_display = ("character", "clue", "attempted_date", "success", "damage_dealt", "focus_lost")


@admin.register(MysteryObstacle)
class MysteryObstacleAdmin(admin.ModelAdmin):
    list_display = ("mystery", "obstacle_type", "skill_used", "dv", "is_ticking_clock")


@admin.register(ObstacleAttempt)
class ObstacleAttemptAdmin(admin.ModelAdmin):
    list_display = ("character", "obstacle", "attempted_date", "success", "focus_lost")


@admin.register(ClueExposure)
class ClueExposureAdmin(admin.ModelAdmin):
    list_display = ("character", "clue", "created_at")
