from django.urls import path

from .views import (
    JobViewSet,
    job_file_crop_view,
    job_file_reprocess_view,
    job_file_update_view,
    presets_custom_create,
    presets_custom_duplicate,
    presets_custom_update,
    presets_view,
    settings_view,
)

# Endpoints principales de jobs. Se mantienen para compatibilidad.
job_list = JobViewSet.as_view({
    'get': 'list',
    'post': 'create',
})
job_detail = JobViewSet.as_view({
    'get': 'retrieve',
})
job_download = JobViewSet.as_view({
    'get': 'download',
})
job_reprocess = JobViewSet.as_view({
    'post': 'reprocess',
})
job_pause = JobViewSet.as_view({
    'post': 'pause',
})
job_resume = JobViewSet.as_view({
    'post': 'resume',
})
job_cancel = JobViewSet.as_view({
    'post': 'cancel',
})
job_delete = JobViewSet.as_view({
    'delete': 'delete_job',
})

urlpatterns = [
    path('presets/', presets_view, name='presets-list'),
    path('presets/custom/', presets_custom_create, name='presets-custom-create'),
    path('presets/custom/<str:preset_id>/', presets_custom_update, name='presets-custom-update'),
    path('presets/custom/<str:preset_id>/duplicate/', presets_custom_duplicate, name='presets-custom-duplicate'),
    path('jobs/', job_list, name='job-list'),
    path('jobs/<int:pk>/', job_detail, name='job-detail'),
    path('jobs/<int:pk>/download/', job_download, name='job-download'),
    path('jobs/<int:pk>/reprocess/', job_reprocess, name='job-reprocess'),
    path('jobs/<int:pk>/pause/', job_pause, name='job-pause'),
    path('jobs/<int:pk>/resume/', job_resume, name='job-resume'),
    path('jobs/<int:pk>/cancel/', job_cancel, name='job-cancel'),
    path('jobs/<int:pk>/delete/', job_delete, name='job-delete'),
    path('settings/', settings_view, name='settings'),
    path('job-files/<int:pk>/crop/', job_file_crop_view, name='job-file-crop'),
    path('job-files/<int:pk>/', job_file_update_view, name='job-file-update'),
    path('job-files/<int:pk>/reprocess/', job_file_reprocess_view, name='job-file-reprocess'),
]
