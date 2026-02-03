from django.db import models


class Job(models.Model):
    """Representa un lote de optimización con preset y progreso global."""
    class Status(models.TextChoices):
        PENDING = 'PENDING'
        PROCESSING = 'PROCESSING'
        PAUSED = 'PAUSED'
        CANCELED = 'CANCELED'
        DONE = 'DONE'
        FAILED = 'FAILED'

    preset = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    progress = models.PositiveIntegerField(default=0)
    total_files = models.PositiveIntegerField(default=0)
    processed_files = models.PositiveIntegerField(default=0)
    result_zip = models.FileField(upload_to='zips/', null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Job {self.id} ({self.status})"


class JobFile(models.Model):
    """Archivo individual dentro de un job con análisis, overrides y salida."""
    class Status(models.TextChoices):
        PENDING = 'PENDING'
        PROCESSING = 'PROCESSING'
        DONE = 'DONE'
        FAILED = 'FAILED'

    job = models.ForeignKey(Job, related_name='files', on_delete=models.CASCADE)
    original_file = models.FileField(upload_to='originals/')
    original_name = models.CharField(max_length=255)
    original_size = models.PositiveIntegerField()
    output_file = models.FileField(upload_to='outputs/', null=True, blank=True)
    output_name = models.CharField(max_length=255, blank=True)
    output_size = models.PositiveIntegerField(null=True, blank=True)
    output_width = models.PositiveIntegerField(null=True, blank=True)
    output_height = models.PositiveIntegerField(null=True, blank=True)
    output_formats = models.JSONField(null=True, blank=True)
    output_variants = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    crop_mode = models.CharField(max_length=20, blank=True)
    crop_x = models.FloatField(null=True, blank=True)
    crop_y = models.FloatField(null=True, blank=True)
    crop_w = models.FloatField(null=True, blank=True)
    crop_h = models.FloatField(null=True, blank=True)
    original_width = models.PositiveIntegerField(null=True, blank=True)
    original_height = models.PositiveIntegerField(null=True, blank=True)
    orientation = models.CharField(max_length=16, blank=True)
    aspect_label = models.CharField(max_length=16, blank=True)
    has_transparency = models.BooleanField(null=True, blank=True)
    analysis_type = models.CharField(max_length=16, blank=True)
    metadata_tags = models.JSONField(null=True, blank=True)
    keep_metadata = models.BooleanField(default=False)
    recommended_preset_id = models.CharField(max_length=64, blank=True)
    recommended_preset_label = models.CharField(max_length=255, blank=True)
    recommended_formats = models.JSONField(null=True, blank=True)
    recommended_quality = models.JSONField(null=True, blank=True)
    recommended_crop_mode = models.CharField(max_length=16, blank=True)
    recommended_crop_reason = models.CharField(max_length=255, blank=True)
    recommended_notes = models.CharField(max_length=255, blank=True)
    selected_preset_id = models.CharField(max_length=64, null=True, blank=True)
    output_format = models.CharField(max_length=16, null=True, blank=True)
    quality_webp = models.PositiveIntegerField(null=True, blank=True)
    quality_jpg = models.PositiveIntegerField(null=True, blank=True)
    quality_avif = models.PositiveIntegerField(null=True, blank=True)
    keep_transparency = models.BooleanField(default=True)
    rename_pattern = models.CharField(max_length=255, null=True, blank=True)
    normalize_lowercase = models.BooleanField(default=True)
    normalize_remove_accents = models.BooleanField(default=True)
    normalize_replace_spaces = models.CharField(max_length=16, default='-')
    normalize_collapse_dashes = models.BooleanField(default=True)
    crop_enabled = models.BooleanField(default=False)
    crop_aspect = models.CharField(max_length=16, blank=True)
    generate_2x = models.BooleanField(default=False)
    generate_sharpened = models.BooleanField(default=False)
    cropped = models.BooleanField(null=True, blank=True)
    metadata_removed = models.BooleanField(null=True, blank=True)

    def __str__(self) -> str:
        return f"JobFile {self.id} ({self.status})"


class AppSettings(models.Model):
    """Configuración global de la app con valores editables desde UI."""
    concurrency = models.PositiveIntegerField(default=4)
    default_remove_metadata = models.BooleanField(default=True)
    default_keep_transparency = models.BooleanField(default=True)
    show_debug_details = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"AppSettings (concurrency={self.concurrency})"


class PresetCustom(models.Model):
    """Preset creado por el equipo para complementar el catálogo base."""
    preset_id = models.CharField(max_length=64, primary_key=True)
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=32)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    aspect = models.CharField(max_length=16)
    type_hint = models.CharField(max_length=16, default='photo')
    density = models.CharField(max_length=32, default='standard')
    recommended_format = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"PresetCustom {self.preset_id}"
