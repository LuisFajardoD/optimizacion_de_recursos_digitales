import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import type { AppSettings, Job, PresetItem } from '../services/api';
import {
  cancelJob,
  deleteJob,
  fetchPresets,
  getSettings,
  listJobs,
  pauseJob,
  resumeJob,
  updateSettings,
} from '../services/api';
import { resolveErrorMessage, useI18n } from '../services/i18n';
import { ConfirmModal } from '../components/ConfirmModal';

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState('');
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [settingsError, setSettingsError] = useState('');
  const [confirmJobId, setConfirmJobId] = useState<number | null>(null);
  const [confirmError, setConfirmError] = useState('');
  const { t, presetLabel, statusLabel, locale } = useI18n();

  const loadJobs = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data);
      setError('');
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorLoadJobs, locale));
    }
  }, [t.errorLoadJobs]);

  useEffect(() => {
    void loadJobs();
    // Refresco periódico para estados de la cola.
    const interval = setInterval(() => void loadJobs(), 4000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  useEffect(() => {
    const loadPresets = async () => {
      try {
        const data = await fetchPresets();
        setPresets(data.presets ?? []);
      } catch {
        setPresets([]);
      }
    };
    void loadPresets();
  }, []);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await getSettings();
        setSettings(data);
        setSettingsError('');
      } catch (err) {
        setSettingsError(resolveErrorMessage(err, t.errorLoadSettings, locale));
      }
    };
    void loadSettings();
  }, [t.errorLoadSettings]);

  const presetsMap = useMemo(() => {
    return presets.reduce<Record<string, string>>((acc, preset) => {
      acc[preset.id] = preset.label;
      return acc;
    }, {});
  }, [presets]);

  const closeConfirm = () => {
    setConfirmJobId(null);
    setConfirmError('');
  };

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t.jobQueueTitle}</h1>
        <p>{t.jobQueueSubtitle}</p>
        <button className="ghost" type="button" onClick={() => void loadJobs()}>
          {t.update}
        </button>
      </header>

      {error && <p className="error">{error}</p>}
      {settingsError && <p className="error">{settingsError}</p>}

      <div className="panel">
        <label className="label">{t.concurrency}</label>
        <select
          value={settings?.concurrency ?? 3}
          onChange={async (event) => {
            const value = Number(event.target.value);
            try {
              // Persistencia inmediata de concurrencia en backend.
              const updated = await updateSettings({ concurrency: value });
              setSettings(updated);
            } catch (err) {
              setSettingsError(resolveErrorMessage(err, t.errorUpdateConcurrency, locale));
            }
          }}
        >
          {Array.from({ length: 10 }).map((_, idx) => {
            const value = idx + 1;
            return (
              <option key={value} value={value}>
                {value}
              </option>
            );
          })}
        </select>
        <p className="muted">{t.concurrencyHelp}</p>
        <p className="muted">{t.concurrencyWarn}</p>
      </div>

      <div className="table">
        <div className="table-row table-header">
          <span>{t.tableId}</span>
          <span>{t.tablePreset}</span>
          <span>{t.tableStatus}</span>
          <span>{t.tableProgress}</span>
          <span>{t.tableFiles}</span>
          <span>{t.tableActions}</span>
        </div>

        {jobs.map((job) => (
          <div className="table-row" key={job.id}>
            <span>#{job.id}</span>
            <span>{presetsMap[job.preset] ?? presetLabel(job.preset)}</span>
            <span className={`status status-cell ${job.status.toLowerCase()}`}>{statusLabel(job.status)}</span>
            <span className="progress-cell">
              <div className="progress">
                <div className="progress-bar" style={{ width: `${job.progress}%` }} />
              </div>
              <span className="progress-text">{job.progress}%</span>
            </span>
            <span className="files-cell">
              {job.processed_files}/{job.total_files}
            </span>
            <span className="job-actions">
              {(job.status === 'DONE' || job.status === 'FAILED' || job.status === 'CANCELED') && (
                <>
                  <Link className="ghost" to={`/jobs/${job.id}`}>
                    {t.view}
                  </Link>
                  <button
                    className="ghost danger"
                    type="button"
                    onClick={async () => {
                      setConfirmJobId(job.id);
                    }}
                  >
                    {t.deleteJob}
                  </button>
                </>
              )}
              {(job.status === 'PENDING' || job.status === 'PROCESSING') && (
                <button
                  className="icon-button"
                  type="button"
                  aria-label={t.pause}
                  title={t.pause}
                  onClick={async () => {
                    try {
                      await pauseJob(job.id);
                      void loadJobs();
                    } catch (err) {
                      setError(resolveErrorMessage(err, t.errorPauseJob, locale));
                    }
                  }}
                >
                  ⏸
                </button>
              )}
              {job.status === 'PAUSED' && (
                <button
                  className="icon-button"
                  type="button"
                  aria-label={t.resume}
                  title={t.resume}
                  onClick={async () => {
                    try {
                      await resumeJob(job.id);
                      void loadJobs();
                    } catch (err) {
                      setError(resolveErrorMessage(err, t.errorResumeJob, locale));
                    }
                  }}
                >
                  ▶
                </button>
              )}
              {(job.status === 'PENDING' || job.status === 'PROCESSING' || job.status === 'PAUSED') && (
                <button
                  className="ghost danger"
                  type="button"
                  onClick={async () => {
                    try {
                      await cancelJob(job.id);
                      void loadJobs();
                    } catch (err) {
                      setError(resolveErrorMessage(err, t.errorCancelJob, locale));
                    }
                  }}
                >
                  {t.cancel}
                </button>
              )}
            </span>
          </div>
        ))}
      </div>

      {jobs.length === 0 && !error && <p className="muted">{t.emptyJobs}</p>}

      <ConfirmModal
        open={confirmJobId !== null}
        title={t.confirmDeleteJobTitle}
        message={t.confirmDeleteJobMessage}
        confirmText={t.deleteJob}
        cancelText={t.cancel}
        danger
        errorText={confirmError}
        onCancel={closeConfirm}
        onConfirm={async () => {
          if (confirmJobId === null) return;
          try {
            await deleteJob(confirmJobId);
            closeConfirm();
            void loadJobs();
          } catch (err) {
            setConfirmError(resolveErrorMessage(err, t.errorDeleteJob, locale));
          }
        }}
      />
    </section>
  );
}
