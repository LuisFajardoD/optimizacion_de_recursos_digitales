from django.contrib import admin

from .models import Job, JobFile


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'preset', 'status', 'progress', 'total_files', 'processed_files', 'created_at')
    list_filter = ('status', 'preset')
    search_fields = ('id',)


@admin.register(JobFile)
class JobFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'original_name', 'status', 'output_name', 'output_size')
    list_filter = ('status',)
    search_fields = ('original_name',)
