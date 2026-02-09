from django.contrib import admin
from .models import Applicant


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = [
        'applicant_id',
        'physics_ict_score',
        'russian_score',
        'math_score',
        'achievements_score',
        'total_score',
        'created_at'
    ]
    search_fields = ['applicant_id']
    list_filter = ['created_at']
    ordering = ['-total_score', 'applicant_id']
    readonly_fields = ['total_score', 'created_at', 'updated_at']