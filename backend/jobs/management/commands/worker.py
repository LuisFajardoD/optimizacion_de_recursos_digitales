import time
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction

from jobs.models import AppSettings, Job
from jobs.services import process_job


class Command(BaseCommand):
    help = 'Procesa jobs pendientes en segundo plano.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Procesa un solo ciclo y sale.')
        parser.add_argument('--sleep', type=int, default=3, help='Segundos entre ciclos.')

    def handle(self, *args, **options):
        """Loop principal del worker con concurrencia configurable."""
        run_once = options['once']
        sleep_time = options['sleep']

        self.stdout.write(self.style.SUCCESS('Worker iniciado.'))
        executor = ThreadPoolExecutor(max_workers=self._get_concurrency())
        futures = []
        while True:
            futures = [f for f in futures if not f.done()]
            concurrency = self._get_concurrency()
            if concurrency != executor._max_workers:
                # Ajuste dinámico cuando cambia la configuración global.
                executor.shutdown(wait=False, cancel_futures=False)
                executor = ThreadPoolExecutor(max_workers=concurrency)

            slots = max(0, concurrency - len(futures))
            if slots > 0:
                jobs = self._next_jobs(slots)
                for job in jobs:
                    futures.append(executor.submit(self._run_job, job.id))

            if not futures and run_once:
                break

            time.sleep(sleep_time)

    def _run_job(self, job_id: int):
        """Ejecuta un job específico aislando conexiones DB por hilo."""
        close_old_connections()
        job = Job.objects.filter(id=job_id).first()
        if not job:
            return
        self.stdout.write(f'Procesando job {job.id}...')
        process_job(job)
        self.stdout.write(f'Job {job.id} terminado con estado {job.status}.')
        close_old_connections()

    def _next_jobs(self, limit: int):
        """Toma jobs PENDING con lock para evitar dobles procesos."""
        with transaction.atomic():
            jobs = list(
                Job.objects.select_for_update()
                .filter(status=Job.Status.PENDING)
                .order_by('created_at')[:limit]
            )
            if not jobs:
                return []
            Job.objects.filter(id__in=[job.id for job in jobs]).update(status=Job.Status.PROCESSING)
            return jobs

    def _get_concurrency(self) -> int:
        """Lee y limita el valor de concurrencia (1..10)."""
        settings_obj, _created = AppSettings.objects.get_or_create(id=1)
        value = settings_obj.concurrency
        if value < 1:
            return 1
        if value > 10:
            return 10
        return value
