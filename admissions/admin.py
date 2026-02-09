from django.contrib import admin
from .models import Program, Application, UploadHistory


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'seats', 'created_at']
    search_fields = ['code', 'name']
    ordering = ['code']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'get_applicant_id', 
        'program', 
        'priority', 
        'consent', 
        'application_date',
        'get_total_score'
    ]
    list_filter = ['application_date', 'program', 'consent', 'priority']
    search_fields = ['applicant__applicant_id']
    date_hierarchy = 'application_date'
    
    def get_applicant_id(self, obj):
        return obj.applicant.applicant_id
    get_applicant_id.short_description = 'ID абитуриента'
    
    def get_total_score(self, obj):
        return obj.applicant.total_score
    get_total_score.short_description = 'Сумма баллов'


@admin.register(UploadHistory)
class UploadHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'upload_date', 
        'competition_date', 
        'records_count', 
        'status'
    ]
    list_filter = ['status', 'competition_date']
    date_hierarchy = 'upload_date'
    readonly_fields = ['upload_date']