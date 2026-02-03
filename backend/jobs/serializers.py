from rest_framework import serializers

from .models import AppSettings, Job, JobFile


class JobFileSerializer(serializers.ModelSerializer):
    """Serializa JobFile con campos calculados para UI y reportes."""
    reduction_percent = serializers.SerializerMethodField()
    final_format = serializers.SerializerMethodField()
    original_url = serializers.SerializerMethodField()
    output_url = serializers.SerializerMethodField()
    width_before = serializers.SerializerMethodField()
    height_before = serializers.SerializerMethodField()
    width_after = serializers.SerializerMethodField()
    height_after = serializers.SerializerMethodField()
    cropped = serializers.SerializerMethodField()
    metadata_removed = serializers.SerializerMethodField()

    class Meta:
        model = JobFile
        fields = [
            'id',
            'original_name',
            'original_size',
            'output_name',
            'output_size',
            'output_width',
            'output_height',
            'output_formats',
            'output_variants',
            'status',
            'error_message',
            'reduction_percent',
            'final_format',
            'original_url',
            'output_url',
            'width_before',
            'height_before',
            'width_after',
            'height_after',
            'cropped',
            'metadata_removed',
            'crop_mode',
            'crop_x',
            'crop_y',
            'crop_w',
            'crop_h',
            'original_width',
            'original_height',
            'orientation',
            'aspect_label',
            'has_transparency',
            'analysis_type',
            'metadata_tags',
            'keep_metadata',
            'recommended_preset_id',
            'recommended_preset_label',
            'recommended_formats',
            'recommended_quality',
            'recommended_crop_mode',
            'recommended_crop_reason',
            'recommended_notes',
            'selected_preset_id',
            'output_format',
            'quality_webp',
            'quality_jpg',
            'quality_avif',
            'keep_transparency',
            'rename_pattern',
            'normalize_lowercase',
            'normalize_remove_accents',
            'normalize_replace_spaces',
            'normalize_collapse_dashes',
            'crop_enabled',
            'crop_aspect',
            'generate_2x',
            'generate_sharpened',
        ]

    def get_reduction_percent(self, obj: JobFile):
        if not obj.output_size or obj.original_size <= 0:
            return None
        return round((1 - (obj.output_size / obj.original_size)) * 100, 2)

    def get_final_format(self, obj: JobFile):
        if not obj.output_name:
            return None
        if '.' not in obj.output_name:
            return None
        return obj.output_name.rsplit('.', 1)[-1].lower()

    def get_original_url(self, obj: JobFile):
        if not obj.original_file:
            return None
        request = self.context.get('request')
        url = obj.original_file.url
        return request.build_absolute_uri(url) if request else url

    def get_output_url(self, obj: JobFile):
        if not obj.output_file:
            return None
        request = self.context.get('request')
        url = obj.output_file.url
        return request.build_absolute_uri(url) if request else url

    def get_width_before(self, obj: JobFile):
        return obj.original_width

    def get_height_before(self, obj: JobFile):
        return obj.original_height

    def get_width_after(self, obj: JobFile):
        return obj.output_width

    def get_height_after(self, obj: JobFile):
        return obj.output_height

    def get_cropped(self, obj: JobFile):
        if obj.cropped is not None:
            return obj.cropped
        return bool(obj.crop_enabled)

    def get_metadata_removed(self, obj: JobFile):
        if obj.metadata_removed is not None:
            return obj.metadata_removed
        return not bool(obj.keep_metadata)


class JobSerializer(serializers.ModelSerializer):
    """Serializador base del job para listados."""
    class Meta:
        model = Job
        fields = [
            'id',
            'preset',
            'status',
            'created_at',
            'started_at',
            'finished_at',
            'progress',
            'total_files',
            'processed_files',
            'error_message',
        ]


class JobDetailSerializer(JobSerializer):
    """Incluye la lista de archivos con sus estados y métricas."""
    files = JobFileSerializer(many=True)

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ['files']


class AppSettingsSerializer(serializers.ModelSerializer):
    """Exposición de configuración global editable desde UI."""
    class Meta:
        model = AppSettings
        fields = [
            'concurrency',
            'default_remove_metadata',
            'default_keep_transparency',
            'show_debug_details',
        ]
